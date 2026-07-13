import re
from collections import Counter
from datetime import date
from math import ceil

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, desc, and_, text
from sqlalchemy.orm import Session

from database.models import (
    Hashtag,
    Video,
    VideoStat,
    FashionItem,
    TrendHistory,
    Prediction,
    video_hashtags,
)
from backend.dependencies import get_db
from backend.security import get_current_user
from ai.tag_filters import BLACKLIST_TAGS


router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


VI_STOPWORDS = {
    "và", "là", "của", "cho", "với", "một", "các", "những", "trong",
    "trên", "này", "đó", "thì", "mình", "bạn", "tôi", "được", "không",
    "the", "and", "for", "you", "with", "this", "that", "from", "outfit",
    "fashion", "video", "tiktok"
}


def get_latest_stats_subquery(db: Session):
    return (
        db.query(
            VideoStat.video_id.label("video_id"),
            func.max(VideoStat.collected_at).label("latest_at"),
        )
        .group_by(VideoStat.video_id)
        .subquery()
    )


def normalize_tag(tag: str):
    return (tag or "").lower().strip().replace("#", "")


def tokenize_text(text_value: str):
    if not text_value:
        return []

    text_value = text_value.lower()
    tokens = re.findall(r"[a-zA-ZÀ-ỹ0-9_]+", text_value)

    result = []

    for token in tokens:
        token = token.strip()

        if len(token) < 2:
            continue

        if token in VI_STOPWORDS:
            continue

        if token in BLACKLIST_TAGS:
            continue

        result.append(token)

    return result


# ============================================================
# 6. Phân tích từ khóa và hashtag liên quan đến thời trang
# ============================================================

@router.get("/fashion-keywords")
def analyze_fashion_keywords(
    limit: int = Query(20, ge=5, le=100),
    hashtag_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    latest_date = db.query(func.max(TrendHistory.date)).scalar()

    target_video_ids_query = None
    target_hashtag = None

    if hashtag_id:
        target_hashtag = (
            db.query(Hashtag)
            .filter(Hashtag.hashtag_id == hashtag_id)
            .first()
        )

        target_video_ids_query = (
            db.query(video_hashtags.c.video_id)
            .filter(video_hashtags.c.hashtag_id == hashtag_id)
            .subquery()
        )

    # 1. Top hashtag
    top_hashtags = []

    if hashtag_id and target_video_ids_query is not None:
        # Related hashtags theo video cùng xuất hiện với hashtag hiện tại
        rows = (
            db.query(
                Hashtag.hashtag_id,
                Hashtag.tag_name,
                func.count(video_hashtags.c.video_id).label("video_count"),
            )
            .join(video_hashtags, Hashtag.hashtag_id == video_hashtags.c.hashtag_id)
            .filter(video_hashtags.c.video_id.in_(target_video_ids_query))
            .filter(Hashtag.hashtag_id != hashtag_id)
            .filter(~func.lower(Hashtag.tag_name).in_(list(BLACKLIST_TAGS)))
            .group_by(Hashtag.hashtag_id, Hashtag.tag_name)
            .order_by(desc("video_count"))
            .limit(limit)
            .all()
        )

        top_hashtags = [
            {
                "hashtag_id": row.hashtag_id,
                "tag_name": row.tag_name,
                "video_count": row.video_count or 0,
                "view_count": 0,
                "view_growth": 0,
                "trend_score": 0,
            }
            for row in rows
        ]

    elif latest_date:
        rows = (
            db.query(
                Hashtag.hashtag_id,
                Hashtag.tag_name,
                TrendHistory.view_count,
                TrendHistory.view_growth,
                TrendHistory.trend_score,
                TrendHistory.video_count,
            )
            .join(TrendHistory, TrendHistory.hashtag_id == Hashtag.hashtag_id)
            .filter(TrendHistory.date == latest_date)
            .filter(~func.lower(Hashtag.tag_name).in_(list(BLACKLIST_TAGS)))
            .order_by(TrendHistory.trend_score.desc())
            .limit(limit)
            .all()
        )

        top_hashtags = [
            {
                "hashtag_id": row.hashtag_id,
                "tag_name": row.tag_name,
                "view_count": row.view_count or 0,
                "view_growth": row.view_growth or 0,
                "trend_score": row.trend_score or 0,
                "video_count": row.video_count or 0,
            }
            for row in rows
        ]

    # 2. Top fashion items
    top_items_query = (
        db.query(
            FashionItem.item_type,
            func.count(func.distinct(FashionItem.video_id)).label("video_count"),
        )
    )

    if hashtag_id and target_video_ids_query is not None:
        top_items_query = top_items_query.filter(
            FashionItem.video_id.in_(target_video_ids_query)
        )

    top_items_rows = (
        top_items_query
        .group_by(FashionItem.item_type)
        .order_by(desc("video_count"))
        .limit(limit)
        .all()
    )

    top_items = [
        {
            "item_type": row.item_type,
            "video_count": row.video_count,
        }
        for row in top_items_rows
    ]

    # 3. Top keywords từ description
    descriptions_query = (
        db.query(Video.description)
        .filter(Video.processing_status == "success")
        .filter(Video.is_analyzed == True)
        .filter(Video.description.isnot(None))
    )

    if hashtag_id and target_video_ids_query is not None:
        descriptions_query = descriptions_query.filter(
            Video.video_id.in_(target_video_ids_query)
        )

    descriptions = descriptions_query.limit(3000).all()

    counter = Counter()

    for row in descriptions:
        counter.update(tokenize_text(row.description))

    top_keywords = [
        {
            "keyword": keyword,
            "count": count,
        }
        for keyword, count in counter.most_common(limit)
    ]

    return {
        "scope": "hashtag" if hashtag_id else "global",
        "hashtag_id": hashtag_id,
        "tag_name": target_hashtag.tag_name if target_hashtag else None,
        "latest_trend_date": latest_date,
        "top_hashtags": top_hashtags,
        "top_fashion_items": top_items,
        "top_keywords": top_keywords,
        "method": "hashtags + video_hashtags + description + fashion_items + blacklist",
    }


# ============================================================
# 7. Phân tích xu hướng theo thời gian
# ============================================================

@router.get("/trend-timeline")
def analyze_trend_timeline(
    hashtag_id: int | None = Query(None),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    selected_hashtags = []

    if hashtag_id:
        hashtag = db.query(Hashtag).filter(Hashtag.hashtag_id == hashtag_id).first()

        if hashtag:
            selected_hashtags = [hashtag]
    else:
        latest_date = db.query(func.max(TrendHistory.date)).scalar()

        if latest_date:
            rows = (
                db.query(Hashtag)
                .join(TrendHistory, TrendHistory.hashtag_id == Hashtag.hashtag_id)
                .filter(TrendHistory.date == latest_date)
                .filter(~func.lower(Hashtag.tag_name).in_(list(BLACKLIST_TAGS)))
                .order_by(TrendHistory.trend_score.desc())
                .limit(limit)
                .all()
            )

            selected_hashtags = rows

    result = []

    for hashtag in selected_hashtags:
        history_rows = (
            db.query(TrendHistory)
            .filter(TrendHistory.hashtag_id == hashtag.hashtag_id)
            .order_by(TrendHistory.date.asc())
            .all()
        )

        result.append(
            {
                "hashtag_id": hashtag.hashtag_id,
                "tag_name": hashtag.tag_name,
                "history_points": len(history_rows),
                "history": [
                    {
                        "date": row.date,
                        "view_count": row.view_count or 0,
                        "view_growth": row.view_growth or 0,
                        "like_growth": row.like_growth or 0,
                        "engagement_rate": row.engagement_rate or 0,
                        "trend_score": row.trend_score or 0,
                        "video_count": row.video_count or 0,
                    }
                    for row in history_rows
                ],
            }
        )

    return {
        "items": result,
        "method": "trend_history.date + view_count + view_growth + engagement_rate + trend_score",
    }


# ============================================================
# 8. Phân tích mức độ tương tác của video
# ============================================================

def build_video_engagement_payload(db: Session, video_id: int):
    video = (
        db.query(Video)
        .filter(Video.video_id == video_id)
        .filter(Video.processing_status == "success")
        .filter(Video.is_analyzed == True)
        .first()
    )

    if not video:
        return None

    stats_rows = (
        db.query(VideoStat)
        .filter(VideoStat.video_id == video_id)
        .order_by(VideoStat.collected_at.asc())
        .all()
    )

    latest = stats_rows[-1] if stats_rows else None

    hashtags = (
        db.query(Hashtag.tag_name)
        .join(video_hashtags, Hashtag.hashtag_id == video_hashtags.c.hashtag_id)
        .filter(video_hashtags.c.video_id == video_id)
        .all()
    )

    items = (
        db.query(FashionItem.item_type)
        .filter(FashionItem.video_id == video_id)
        .all()
    )

    if latest:
        engagement_rate = (
            (
                (latest.like_count or 0)
                + (latest.comment_count or 0)
                + (latest.share_count or 0)
            )
            * 100.0
            / ((latest.view_count or 0) + 1)
        )
    else:
        engagement_rate = 0

    return {
        "video_id": video.video_id,
        "description": video.description,
        "video_url": video.video_url,
        "cover_url": video.cover_url,
        "processing_status": video.processing_status,
        "hashtags": [h[0] for h in hashtags],
        "fashion_items": [i[0] for i in items],
        "latest_stats": {
            "view_count": latest.view_count if latest else getattr(video, "view_count", 0),
            "like_count": latest.like_count if latest else getattr(video, "like_count", 0),
            "comment_count": latest.comment_count if latest else getattr(video, "comment_count", 0),
            "share_count": latest.share_count if latest else getattr(video, "share_count", 0),
            "collected_at": latest.collected_at if latest else None,
            "engagement_rate": engagement_rate,
        },
        "stats_history": [
            {
                "collected_at": row.collected_at,
                "view_count": row.view_count or 0,
                "like_count": row.like_count or 0,
                "comment_count": row.comment_count or 0,
                "share_count": row.share_count or 0,
                "engagement_rate": (
                    (
                        (row.like_count or 0)
                        + (row.comment_count or 0)
                        + (row.share_count or 0)
                    )
                    * 100.0
                    / ((row.view_count or 0) + 1)
                ),
            }
            for row in stats_rows
        ],
        "method": "video_stats + like/comment/share + engagement_rate",
    }   

@router.get("/engagement")
def analyze_engagement(
    limit: int = Query(20, ge=5, le=100),
    video_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if video_id:
        payload = build_video_engagement_payload(db, video_id)

        if not payload:
            return {
                "video_id": video_id,
                "found": False,
                "message": "Video not found",
            }

        return {
            "found": True,
            "item": payload,
        }

    latest_stats = get_latest_stats_subquery(db)

    engagement_expr = (
        (
            func.coalesce(VideoStat.like_count, 0)
            + func.coalesce(VideoStat.comment_count, 0)
            + func.coalesce(VideoStat.share_count, 0)
        )
        * 100.0
        / (func.coalesce(VideoStat.view_count, 0) + 1)
    ).label("engagement_rate")

    video_rows = (
        db.query(
            Video.video_id,
            Video.description,
            Video.video_url,
            Video.cover_url,
            Video.processing_status,
            VideoStat.view_count,
            VideoStat.like_count,
            VideoStat.comment_count,
            VideoStat.share_count,
            engagement_expr,
        )
        .join(latest_stats, latest_stats.c.video_id == Video.video_id)
        .join(
            VideoStat,
            and_(
                VideoStat.video_id == latest_stats.c.video_id,
                VideoStat.collected_at == latest_stats.c.latest_at,
            ),
        )
        .filter(Video.processing_status == "success")
        .filter(Video.is_analyzed == True)
        .order_by(desc(engagement_expr))
        .limit(limit)
        .all()
    )

    top_videos = []

    for row in video_rows:
        hashtags = (
            db.query(Hashtag.tag_name)
            .join(video_hashtags, Hashtag.hashtag_id == video_hashtags.c.hashtag_id)
            .filter(video_hashtags.c.video_id == row.video_id)
            .all()
        )

        items = (
            db.query(FashionItem.item_type)
            .filter(FashionItem.video_id == row.video_id)
            .all()
        )

        top_videos.append(
            {
                "video_id": row.video_id,
                "description": row.description,
                "video_url": row.video_url,
                "cover_url": row.cover_url,
                "processing_status": row.processing_status,
                "view_count": row.view_count or 0,
                "like_count": row.like_count or 0,
                "comment_count": row.comment_count or 0,
                "share_count": row.share_count or 0,
                "engagement_rate": row.engagement_rate or 0,
                "hashtags": [h[0] for h in hashtags],
                "fashion_items": [i[0] for i in items],
            }
        )

    latest_date = db.query(func.max(TrendHistory.date)).scalar()

    top_hashtag_engagement = []

    if latest_date:
        rows = (
            db.query(
                Hashtag.hashtag_id,
                Hashtag.tag_name,
                TrendHistory.engagement_rate,
                TrendHistory.view_count,
                TrendHistory.view_growth,
                TrendHistory.trend_score,
            )
            .join(TrendHistory, TrendHistory.hashtag_id == Hashtag.hashtag_id)
            .filter(TrendHistory.date == latest_date)
            .filter(~func.lower(Hashtag.tag_name).in_(list(BLACKLIST_TAGS)))
            .order_by(TrendHistory.engagement_rate.desc())
            .limit(limit)
            .all()
        )

        top_hashtag_engagement = [
            {
                "hashtag_id": row.hashtag_id,
                "tag_name": row.tag_name,
                "engagement_rate": row.engagement_rate or 0,
                "view_count": row.view_count or 0,
                "view_growth": row.view_growth or 0,
                "trend_score": row.trend_score or 0,
            }
            for row in rows
        ]

    return {
        "top_videos_by_engagement": top_videos,
        "top_hashtags_by_engagement": top_hashtag_engagement,
        "method": "video_stats + like/comment/share + trend_history.engagement_rate",
    }


# ============================================================
# 13. Dự đoán xu hướng thời trang trong tương lai
# ============================================================

@router.get("/prediction-summary")
def prediction_summary(
    limit: int = Query(20, ge=5, le=100),
    model_version: str = Query("lstm_trend_history_growth_v2"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    latest_prediction_date = (
        db.query(func.max(Prediction.prediction_date))
        .filter(Prediction.model_version == model_version)
        .scalar()
    )

    if not latest_prediction_date:
        return {
            "model_version": model_version,
            "prediction_date": None,
            "items": [],
        }

    rows = (
        db.query(
            Prediction.prediction_id,
            Prediction.hashtag_id,
            Hashtag.tag_name,
            Prediction.prediction_type,
            Prediction.prediction_date,
            Prediction.predicted_for_date,
            Prediction.predicted_value,
            Prediction.model_version,
        )
        .join(Hashtag, Hashtag.hashtag_id == Prediction.hashtag_id)
        .filter(Prediction.model_version == model_version)
        .filter(Prediction.prediction_date == latest_prediction_date)
        .filter(Prediction.prediction_type == "view_growth")
        .filter(~func.lower(Hashtag.tag_name).in_(list(BLACKLIST_TAGS)))
        .order_by(Prediction.predicted_value.desc())
        .limit(limit)
        .all()
    )

    return {
        "model_version": model_version,
        "prediction_date": latest_prediction_date,
        "items": [
            {
                "prediction_id": row.prediction_id,
                "hashtag_id": row.hashtag_id,
                "tag_name": row.tag_name,
                "prediction_type": row.prediction_type,
                "prediction_date": row.prediction_date,
                "predicted_for_date": row.predicted_for_date,
                "predicted_growth": row.predicted_value or 0,
                "model_version": row.model_version,
            }
            for row in rows
        ],
        "method": "LSTM v2 input trend_history sequence -> output predicted view_growth -> predictions",
    }


# ============================================================
# 14. So sánh xu hướng giữa các giai đoạn
# ============================================================

def aggregate_period(db: Session, start_date: date, end_date: date):
    rows = (
        db.query(
            Hashtag.hashtag_id,
            Hashtag.tag_name,
            func.sum(TrendHistory.view_growth).label("total_view_growth"),
            func.avg(TrendHistory.view_growth).label("avg_view_growth"),
            func.avg(TrendHistory.engagement_rate).label("avg_engagement_rate"),
            func.avg(TrendHistory.trend_score).label("avg_trend_score"),
            func.count(func.distinct(TrendHistory.date)).label("history_points"),
        )
        .join(TrendHistory, TrendHistory.hashtag_id == Hashtag.hashtag_id)
        .filter(TrendHistory.date >= start_date)
        .filter(TrendHistory.date <= end_date)
        .filter(~func.lower(Hashtag.tag_name).in_(list(BLACKLIST_TAGS)))
        .group_by(Hashtag.hashtag_id, Hashtag.tag_name)
        .all()
    )

    return {
        row.hashtag_id: {
            "hashtag_id": row.hashtag_id,
            "tag_name": row.tag_name,
            "total_view_growth": float(row.total_view_growth or 0),
            "avg_view_growth": float(row.avg_view_growth or 0),
            "avg_engagement_rate": float(row.avg_engagement_rate or 0),
            "avg_trend_score": float(row.avg_trend_score or 0),
            "history_points": int(row.history_points or 0),
        }
        for row in rows
    }


@router.get("/period-comparison")
def compare_periods(
    start_a: date = Query(...),
    end_a: date = Query(...),
    start_b: date = Query(...),
    end_b: date = Query(...),
    limit: int = Query(30, ge=5, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    period_a = aggregate_period(db, start_a, end_a)
    period_b = aggregate_period(db, start_b, end_b)

    hashtag_ids = set(period_a.keys()) | set(period_b.keys())

    comparison = []

    for hashtag_id in hashtag_ids:
        a = period_a.get(
            hashtag_id,
            {
                "hashtag_id": hashtag_id,
                "tag_name": period_b.get(hashtag_id, {}).get("tag_name"),
                "total_view_growth": 0,
                "avg_view_growth": 0,
                "avg_engagement_rate": 0,
                "avg_trend_score": 0,
                "history_points": 0,
            },
        )

        b = period_b.get(
            hashtag_id,
            {
                "hashtag_id": hashtag_id,
                "tag_name": a.get("tag_name"),
                "total_view_growth": 0,
                "avg_view_growth": 0,
                "avg_engagement_rate": 0,
                "avg_trend_score": 0,
                "history_points": 0,
            },
        )

        comparison.append(
            {
                "hashtag_id": hashtag_id,
                "tag_name": a["tag_name"] or b["tag_name"],
                "period_a": a,
                "period_b": b,
                "delta_total_view_growth": b["total_view_growth"] - a["total_view_growth"],
                "delta_avg_view_growth": b["avg_view_growth"] - a["avg_view_growth"],
                "delta_engagement_rate": b["avg_engagement_rate"] - a["avg_engagement_rate"],
                "delta_trend_score": b["avg_trend_score"] - a["avg_trend_score"],
            }
        )

    comparison.sort(key=lambda item: item["delta_trend_score"], reverse=True)

    return {
        "period_a": {
            "start": start_a,
            "end": end_a,
        },
        "period_b": {
            "start": start_b,
            "end": end_b,
        },
        "items": comparison[:limit],
        "method": "Compare view_growth + trend_score + engagement_rate from trend_history",
    }


# ============================================================
# 15. Lưu lịch sử phân tích
# ============================================================

def safe_table_count(db: Session, table_name: str):
    allowed_tables = {
        "trend_history",
        "predictions",
        "crawler_jobs",
        "ai_analysis",
    }

    if table_name not in allowed_tables:
        return 0

    exists = db.execute(
        text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
    ).scalar()

    if not exists:
        return 0

    return db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0


@router.get("/analysis-history")
def get_analysis_history(
    limit: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    latest_trend_history = (
        db.query(TrendHistory, Hashtag.tag_name)
        .join(Hashtag, Hashtag.hashtag_id == TrendHistory.hashtag_id)
        .order_by(TrendHistory.date.desc(), TrendHistory.trend_score.desc())
        .limit(limit)
        .all()
    )

    latest_predictions = (
        db.query(Prediction, Hashtag.tag_name)
        .join(Hashtag, Hashtag.hashtag_id == Prediction.hashtag_id)
        .order_by(Prediction.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "summary": {
            "trend_history_rows": safe_table_count(db, "trend_history"),
            "prediction_rows": safe_table_count(db, "predictions"),
            "crawler_job_rows": safe_table_count(db, "crawler_jobs"),
            "ai_analysis_rows": safe_table_count(db, "ai_analysis"),
        },
        "latest_trend_history": [
            {
                "hashtag_id": row.TrendHistory.hashtag_id,
                "tag_name": row.tag_name,
                "date": row.TrendHistory.date,
                "view_count": row.TrendHistory.view_count or 0,
                "view_growth": row.TrendHistory.view_growth or 0,
                "engagement_rate": row.TrendHistory.engagement_rate or 0,
                "trend_score": row.TrendHistory.trend_score or 0,
            }
            for row in latest_trend_history
        ],
        "latest_predictions": [
            {
                "prediction_id": row.Prediction.prediction_id,
                "hashtag_id": row.Prediction.hashtag_id,
                "tag_name": row.tag_name,
                "prediction_date": row.Prediction.prediction_date,
                "predicted_for_date": row.Prediction.predicted_for_date,
                "predicted_value": row.Prediction.predicted_value or 0,
                "model_version": row.Prediction.model_version,
                "created_at": row.Prediction.created_at,
            }
            for row in latest_predictions
        ],
        "method": "trend_history + predictions + crawler_jobs + ai_analysis if available",
    }