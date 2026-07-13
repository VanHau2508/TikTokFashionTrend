import argparse
import logging
import sys
from datetime import datetime, timedelta, time, timezone

from ai.tag_filters import BLACKLIST_TAGS
from sqlalchemy import func, and_, case, text
from sqlalchemy.orm import Session, aliased

from database.models import (
    Hashtag,
    Video,
    VideoStat,
    TrendHistory,
    video_hashtags,
)
from database.config import SessionLocal


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class TrendHistoryBuilder:
    """
    Build trend_history từ video_stats.

    Quy tắc quan trọng của bản này:
    - view_count / like_count / comment_count / share_count vẫn là tổng số liệu hiện tại
      của các video hợp lệ trong hashtag tại cuối ngày.
    - view_growth / like_growth / trend_score được tính theo DELTA TỪNG VIDEO:
        latest_snapshot_trong_ngày - latest_snapshot_trước_ngày_đó
    - Video mới crawl lần đầu chưa có snapshot trước đó sẽ KHÔNG được tính vào growth
      trong ngày đầu tiên. Điều này tránh lỗi:
        "view tích lũy có sẵn của video mới" bị hiểu nhầm là "view tăng thêm hôm nay".

    Có 2 cách dùng chính:
    1) Rebuild theo khoảng ngày lịch sử:
       build_daily_history(start_date_str="2026-05-10", end_date_str="2026-06-22", clean_before_build=True)

    2) Incremental hằng ngày:
       build_today()
       hoặc build_missing_until_today()
    """

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _parse_date(value):
        if value is None:
            return None
        if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
            return value
        return datetime.strptime(str(value), "%Y-%m-%d").date()

    def _get_latest_trend_date(self):
        return self.db.query(func.max(TrendHistory.date)).scalar()

    def refresh_hashtag_cache_from_trend_history(self):
        """
        Cập nhật cache mới nhất cho bảng hashtags từ trend_history.

        Bảng trend_history vẫn là nguồn dữ liệu chính cho LSTM và phân tích theo ngày.
        Ba trường trong hashtags chỉ là cache/tóm tắt nhanh để frontend hoặc truy vấn
        danh sách hashtag không bị NULL và có thể sắp xếp nhanh.

        Mapping:
        - hashtags.trending_score <- trend_history.trend_score mới nhất
        - hashtags.video_count    <- trend_history.video_count mới nhất
        - hashtags.total_views    <- trend_history.view_count mới nhất
        """
        logger.info("🔄 Cập nhật cache hashtags từ trend_history mới nhất...")

        update_latest_sql = text("""
            WITH latest_history AS (
                SELECT DISTINCT ON (hashtag_id)
                    hashtag_id,
                    date,
                    trend_score,
                    video_count,
                    view_count
                FROM trend_history
                ORDER BY hashtag_id, date DESC
            )
            UPDATE hashtags h
            SET
                trending_score = COALESCE(lh.trend_score, 0),
                video_count = COALESCE(lh.video_count, 0),
                total_views = COALESCE(lh.view_count, 0),
                last_seen = lh.date::timestamp AT TIME ZONE 'UTC'
            FROM latest_history lh
            WHERE h.hashtag_id = lh.hashtag_id;
        """)

        normalize_null_sql = text("""
            UPDATE hashtags
            SET
                trending_score = COALESCE(trending_score, 0),
                video_count = COALESCE(video_count, 0),
                total_views = COALESCE(total_views, 0)
            WHERE trending_score IS NULL
               OR video_count IS NULL
               OR total_views IS NULL;
        """)

        result = self.db.execute(update_latest_sql)
        updated_from_history = result.rowcount or 0

        null_result = self.db.execute(normalize_null_sql)
        normalized_null_rows = null_result.rowcount or 0

        self.db.commit()

        logger.info(
            "✅ Hashtag cache updated: "
            f"updated_from_history={updated_from_history}, "
            f"normalized_null_rows={normalized_null_rows}"
        )

        return {
            "updated_from_history": updated_from_history,
            "normalized_null_rows": normalized_null_rows,
        }

    def _seed_previous_engagement_map(self, start_date):
        """
        Chỉ dùng để tính engagement_growth dựa trên trend_history gần nhất trước start_date.
        Lưu ý: view_growth/like_growth KHÔNG dùng map này nữa, mà dùng delta từng video.
        """
        latest_before_subq = (
            self.db.query(
                TrendHistory.hashtag_id.label("hashtag_id"),
                func.max(TrendHistory.date).label("latest_date"),
            )
            .filter(TrendHistory.date < start_date)
            .group_by(TrendHistory.hashtag_id)
            .subquery()
        )

        rows = (
            self.db.query(TrendHistory)
            .join(
                latest_before_subq,
                and_(
                    TrendHistory.hashtag_id == latest_before_subq.c.hashtag_id,
                    TrendHistory.date == latest_before_subq.c.latest_date,
                ),
            )
            .all()
        )

        previous_map = {}
        for row in rows:
            previous_map[row.hashtag_id] = {
                "engagement_rate": float(row.engagement_rate or 0),
                "date": row.date,
            }

        logger.info(f"📌 Seed previous engagement rows: {len(previous_map)}")
        return previous_map

    def _eligible_videos_subquery(
        self,
        start_date,
        end_date,
        min_distinct_stat_days=4,
        eligibility_lookback_days=30,
    ):
        """
        Video đủ điều kiện nếu:
        - YOLO success
        - is_in_scope = True
        - có tối thiểu min_distinct_stat_days ngày có snapshot trong lookback window.

        Lý do: nếu build riêng hôm nay, không thể yêu cầu video có 4 ngày snapshot trong đúng hôm nay.
        """
        eligibility_start_date = start_date - timedelta(days=max(0, int(eligibility_lookback_days)))

        return (
            self.db.query(VideoStat.video_id.label("video_id"))
            .join(Video, Video.video_id == VideoStat.video_id)
            .filter(
                Video.processing_status == "success",
                Video.is_analyzed == True,
                Video.is_in_scope == True,
                func.date(VideoStat.collected_at) >= eligibility_start_date,
                func.date(VideoStat.collected_at) <= end_date,
            )
            .group_by(VideoStat.video_id)
            .having(
                func.count(func.distinct(func.date(VideoStat.collected_at)))
                >= min_distinct_stat_days
            )
            .subquery()
        )

    def build_daily_history(
        self,
        start_date_str="2026-05-09",
        end_date_str="2026-05-19",
        min_distinct_stat_days=4,
        clean_before_build=False,
        should_stop=None,
        eligibility_lookback_days=30,
        seed_previous_from_db=True,
    ):
        def stop_requested():
            return should_stop is not None and should_stop()

        start_date = self._parse_date(start_date_str)
        end_date = self._parse_date(end_date_str)

        if start_date > end_date:
            return {
                "status": "completed",
                "message": "Không có ngày nào cần build.",
                "start_date": str(start_date),
                "end_date": str(end_date),
                "built_days": 0,
            }

        logger.info("=" * 80)
        logger.info("🚀 BUILD TREND_HISTORY - DELTA SAFE")
        logger.info("=" * 80)
        logger.info(f"📅 Date range: {start_date} → {end_date}")
        logger.info(f"📌 Min distinct stat days/video: {min_distinct_stat_days}")
        logger.info(f"📌 Eligibility lookback days: {eligibility_lookback_days}")
        logger.info("📌 view_count: latest snapshot per video before end-of-day")
        logger.info("📌 view_growth: sum(delta per video), new videos first snapshot = 0 growth")
        logger.info("📌 Rule: YOLO success + is_in_scope videos only")
        logger.info("📌 Rule: blacklist generic hashtags")

        if clean_before_build:
            logger.warning(f"🧹 Xóa trend_history từ {start_date} đến {end_date} trước khi build...")
            self.db.query(TrendHistory).filter(
                TrendHistory.date >= start_date,
                TrendHistory.date <= end_date,
            ).delete(synchronize_session=False)
            self.db.commit()
            logger.info("✅ Đã xóa dữ liệu trend_history cũ trong khoảng ngày.")

        eligible_videos = self._eligible_videos_subquery(
            start_date=start_date,
            end_date=end_date,
            min_distinct_stat_days=min_distinct_stat_days,
            eligibility_lookback_days=eligibility_lookback_days,
        )
        eligible_count = self.db.query(func.count()).select_from(eligible_videos).scalar() or 0
        logger.info(f"✅ Eligible videos: {eligible_count}")

        previous_engagement_map = (
            self._seed_previous_engagement_map(start_date)
            if seed_previous_from_db
            else {}
        )

        current_date = start_date
        built_days = 0
        total_created = 0
        total_updated = 0

        while current_date <= end_date:
            if stop_requested():
                logger.warning("🛑 Build trend_history đã bị dừng bởi admin.")
                return {
                    "status": "cancelled",
                    "message": "Task đã được dừng bởi admin.",
                    "last_date": str(current_date),
                    "built_days": built_days,
                }

            logger.info("-" * 80)
            logger.info(f"⏳ Đang xử lý ngày: {current_date}")

            start_of_day = datetime.combine(current_date, time.min, tzinfo=timezone.utc)
            next_day = current_date + timedelta(days=1)
            end_of_day = datetime.combine(next_day, time.min, tzinfo=timezone.utc)

            try:
                CurrentStat = aliased(VideoStat)
                PreviousStat = aliased(VideoStat)

                # Snapshot mới nhất của từng video trước cuối ngày hiện tại.
                current_latest_subquery = (
                    self.db.query(
                        VideoStat.video_id.label("video_id"),
                        func.max(VideoStat.collected_at).label("current_collected_at"),
                    )
                    .join(eligible_videos, eligible_videos.c.video_id == VideoStat.video_id)
                    .filter(VideoStat.collected_at < end_of_day)
                    .group_by(VideoStat.video_id)
                    .subquery()
                )

                # Snapshot mới nhất của từng video trước đầu ngày hiện tại.
                # Nếu không có snapshot trước ngày đó => video mới, growth ngày đầu = 0.
                previous_latest_subquery = (
                    self.db.query(
                        VideoStat.video_id.label("video_id"),
                        func.max(VideoStat.collected_at).label("previous_collected_at"),
                    )
                    .join(eligible_videos, eligible_videos.c.video_id == VideoStat.video_id)
                    .filter(VideoStat.collected_at < start_of_day)
                    .group_by(VideoStat.video_id)
                    .subquery()
                )

                view_delta = case(
                    (
                        PreviousStat.video_id.isnot(None),
                        func.greatest(
                            func.coalesce(CurrentStat.view_count, 0)
                            - func.coalesce(PreviousStat.view_count, 0),
                            0,
                        ),
                    ),
                    else_=0,
                )

                like_delta = case(
                    (
                        PreviousStat.video_id.isnot(None),
                        func.greatest(
                            func.coalesce(CurrentStat.like_count, 0)
                            - func.coalesce(PreviousStat.like_count, 0),
                            0,
                        ),
                    ),
                    else_=0,
                )

                comment_delta = case(
                    (
                        PreviousStat.video_id.isnot(None),
                        func.greatest(
                            func.coalesce(CurrentStat.comment_count, 0)
                            - func.coalesce(PreviousStat.comment_count, 0),
                            0,
                        ),
                    ),
                    else_=0,
                )

                share_delta = case(
                    (
                        PreviousStat.video_id.isnot(None),
                        func.greatest(
                            func.coalesce(CurrentStat.share_count, 0)
                            - func.coalesce(PreviousStat.share_count, 0),
                            0,
                        ),
                    ),
                    else_=0,
                )

                new_video_case = case(
                    (PreviousStat.video_id.is_(None), Video.video_id),
                    else_=None,
                )

                new_video_views = case(
                    (
                        PreviousStat.video_id.is_(None),
                        func.coalesce(CurrentStat.view_count, 0),
                    ),
                    else_=0,
                )

                stats = (
                    self.db.query(
                        Hashtag.hashtag_id.label("hashtag_id"),
                        Hashtag.tag_name.label("tag_name"),

                        # Tổng hiện tại theo snapshot mới nhất trước cuối ngày.
                        func.sum(func.coalesce(CurrentStat.view_count, 0)).label("views"),
                        func.sum(func.coalesce(CurrentStat.like_count, 0)).label("likes"),
                        func.sum(func.coalesce(CurrentStat.comment_count, 0)).label("comments"),
                        func.sum(func.coalesce(CurrentStat.share_count, 0)).label("shares"),
                        func.count(func.distinct(Video.video_id)).label("video_count"),

                        # Growth thật theo delta từng video.
                        func.sum(view_delta).label("view_growth"),
                        func.sum(like_delta).label("like_growth"),
                        func.sum(comment_delta).label("comment_growth"),
                        func.sum(share_delta).label("share_growth"),

                        # Chỉ để log/debug, không lưu DB.
                        func.count(func.distinct(new_video_case)).label("new_video_count"),
                        func.sum(new_video_views).label("new_video_views"),
                    )
                    .join(video_hashtags, Hashtag.hashtag_id == video_hashtags.c.hashtag_id)
                    .join(Video, video_hashtags.c.video_id == Video.video_id)
                    .join(eligible_videos, eligible_videos.c.video_id == Video.video_id)
                    .join(
                        current_latest_subquery,
                        current_latest_subquery.c.video_id == Video.video_id,
                    )
                    .join(
                        CurrentStat,
                        and_(
                            CurrentStat.video_id == current_latest_subquery.c.video_id,
                            CurrentStat.collected_at == current_latest_subquery.c.current_collected_at,
                        ),
                    )
                    .outerjoin(
                        previous_latest_subquery,
                        previous_latest_subquery.c.video_id == Video.video_id,
                    )
                    .outerjoin(
                        PreviousStat,
                        and_(
                            PreviousStat.video_id == previous_latest_subquery.c.video_id,
                            PreviousStat.collected_at == previous_latest_subquery.c.previous_collected_at,
                        ),
                    )
                    .filter(Video.processing_status == "success")
                    .filter(Video.is_in_scope == True)
                    .filter(Video.is_analyzed == True)
                    .filter(~func.lower(Hashtag.tag_name).in_(list(BLACKLIST_TAGS)))
                    .group_by(Hashtag.hashtag_id, Hashtag.tag_name)
                    .all()
                )

                if not stats:
                    logger.warning(f"⚠️ Ngày {current_date} không có dữ liệu.")
                    current_date += timedelta(days=1)
                    continue

                created_count = 0
                updated_count = 0
                total_new_video_views_debug = 0
                total_new_video_count_debug = 0

                for s in stats:
                    if stop_requested():
                        logger.warning("🛑 Admin đã yêu cầu dừng khi đang ghi trend_history.")
                        self.db.rollback()
                        return {
                            "status": "cancelled",
                            "message": "Task đã được dừng bởi admin.",
                            "last_date": str(current_date),
                            "built_days": built_days,
                        }

                    views = int(s.views or 0)
                    likes = int(s.likes or 0)
                    comments = int(s.comments or 0)
                    shares = int(s.shares or 0)
                    video_count = int(s.video_count or 0)

                    view_growth = int(s.view_growth or 0)
                    like_growth = int(s.like_growth or 0)
                    comment_growth = int(s.comment_growth or 0)
                    share_growth = int(s.share_growth or 0)

                    total_new_video_count_debug += int(s.new_video_count or 0)
                    total_new_video_views_debug += int(s.new_video_views or 0)

                    engagement_rate = ((likes + comments + shares) / (views + 1)) * 100

                    previous = previous_engagement_map.get(s.hashtag_id)
                    if previous:
                        engagement_growth = (
                            engagement_rate - float(previous["engagement_rate"] or 0)
                        )
                    else:
                        engagement_growth = 0

                    # Dùng delta cho trend_score để không bị video mới crawl làm phình điểm.
                    trend_score = (
                        view_growth * 0.45
                        + like_growth * 0.25
                        + comment_growth * 0.15
                        + share_growth * 0.15
                    )

                    existing = (
                        self.db.query(TrendHistory)
                        .filter(
                            TrendHistory.hashtag_id == s.hashtag_id,
                            TrendHistory.date == current_date,
                        )
                        .first()
                    )

                    if existing:
                        existing.view_count = views
                        existing.like_count = likes
                        existing.comment_count = comments
                        existing.share_count = shares
                        existing.video_count = video_count
                        existing.engagement_rate = engagement_rate
                        existing.view_growth = view_growth
                        existing.like_growth = like_growth
                        existing.engagement_growth = engagement_growth
                        existing.trend_score = trend_score
                        existing.is_imputed = False
                        existing.imputation_method = "raw_from_video_stats_delta_safe"
                        existing.data_quality_score = 1.0
                        updated_count += 1
                    else:
                        new_record = TrendHistory(
                            hashtag_id=s.hashtag_id,
                            date=current_date,
                            view_count=views,
                            like_count=likes,
                            comment_count=comments,
                            share_count=shares,
                            video_count=video_count,
                            engagement_rate=engagement_rate,
                            view_growth=view_growth,
                            like_growth=like_growth,
                            engagement_growth=engagement_growth,
                            trend_score=trend_score,
                            is_imputed=False,
                            imputation_method="raw_from_video_stats_delta_safe",
                            data_quality_score=1.0,
                        )
                        self.db.add(new_record)
                        created_count += 1

                    previous_engagement_map[s.hashtag_id] = {
                        "engagement_rate": engagement_rate,
                        "date": current_date,
                    }

                self.db.commit()
                built_days += 1
                total_created += created_count
                total_updated += updated_count

                logger.info(
                    f"✅ {current_date}: hashtags={len(stats)}, "
                    f"created={created_count}, updated={updated_count}, "
                    f"new_videos_seen={total_new_video_count_debug}, "
                    f"new_video_views_excluded_from_growth={total_new_video_views_debug:,}"
                )

            except Exception as e:
                self.db.rollback()
                logger.error(f"❌ Lỗi tại ngày {current_date}: {e}")
                raise

            current_date += timedelta(days=1)

        hashtag_cache_result = self.refresh_hashtag_cache_from_trend_history()

        logger.info("=" * 80)
        logger.info("🏁 Hoàn tất tạo/cập nhật TrendHistory.")
        logger.info(f"📌 Built days: {built_days}")
        logger.info(f"📌 Created: {total_created} | Updated: {total_updated}")
        logger.info(
            "📌 Hashtag cache: "
            f"updated_from_history={hashtag_cache_result.get('updated_from_history', 0)} | "
            f"normalized_null_rows={hashtag_cache_result.get('normalized_null_rows', 0)}"
        )
        logger.info("=" * 80)

        return {
            "status": "completed",
            "message": "Build trend_history completed.",
            "start_date": str(start_date),
            "end_date": str(end_date),
            "built_days": built_days,
            "created": total_created,
            "updated": total_updated,
            "hashtag_cache": hashtag_cache_result,
        }

    def build_today(
        self,
        min_distinct_stat_days=4,
        eligibility_lookback_days=30,
        clean_before_build=False,
        should_stop=None,
    ):
        today = datetime.now(timezone.utc).date()
        return self.build_daily_history(
            start_date_str=str(today),
            end_date_str=str(today),
            min_distinct_stat_days=min_distinct_stat_days,
            clean_before_build=clean_before_build,
            should_stop=should_stop,
            eligibility_lookback_days=eligibility_lookback_days,
            seed_previous_from_db=True,
        )

    def build_missing_until_today(
        self,
        min_distinct_stat_days=4,
        eligibility_lookback_days=30,
        should_stop=None,
    ):
        """
        Build từ ngày sau max(trend_history.date) đến hôm nay.
        Nếu đã có hôm nay rồi thì chỉ update hôm nay để lấy snapshot mới hơn trong ngày.
        """
        today = datetime.now(timezone.utc).date()
        latest_date = self._get_latest_trend_date()

        if latest_date is None:
            raise ValueError(
                "Chưa có trend_history cũ. Hãy chạy full rebuild lần đầu với start_date/end_date."
            )

        start_date = latest_date + timedelta(days=1)
        if start_date > today:
            start_date = today

        return self.build_daily_history(
            start_date_str=str(start_date),
            end_date_str=str(today),
            min_distinct_stat_days=min_distinct_stat_days,
            clean_before_build=False,
            should_stop=should_stop,
            eligibility_lookback_days=eligibility_lookback_days,
            seed_previous_from_db=True,
        )


def _build_arg_parser():
    parser = argparse.ArgumentParser(description="Build trend_history from video_stats")
    parser.add_argument("--start-date", default=None, help="YYYY-MM-DD")
    parser.add_argument("--end-date", default=None, help="YYYY-MM-DD")
    parser.add_argument("--today", action="store_true", help="Chỉ build/update ngày hôm nay")
    parser.add_argument("--missing-until-today", action="store_true", help="Build các ngày còn thiếu từ max(date)+1 đến hôm nay")
    parser.add_argument("--min-days", type=int, default=4, help="Số ngày snapshot tối thiểu/video")
    parser.add_argument("--lookback-days", type=int, default=30, help="Số ngày lookback để xét video đủ điều kiện")
    parser.add_argument("--clean", action="store_true", help="Xóa trend_history trong khoảng trước khi build")
    return parser


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    db_session = SessionLocal()

    try:
        builder = TrendHistoryBuilder(db_session)

        if args.today:
            builder.build_today(
                min_distinct_stat_days=args.min_days,
                eligibility_lookback_days=args.lookback_days,
                clean_before_build=args.clean,
            )
        elif args.missing_until_today:
            builder.build_missing_until_today(
                min_distinct_stat_days=args.min_days,
                eligibility_lookback_days=args.lookback_days,
            )
        else:
            start_date = args.start_date or "2026-05-10"
            end_date = args.end_date or str(datetime.now(timezone.utc).date())
            builder.build_daily_history(
                start_date_str=start_date,
                end_date_str=end_date,
                min_distinct_stat_days=args.min_days,
                clean_before_build=args.clean,
                eligibility_lookback_days=args.lookback_days,
                seed_previous_from_db=True,
            )
    finally:
        db_session.close()
