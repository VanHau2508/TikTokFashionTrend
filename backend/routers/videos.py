from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, desc, and_, or_
from sqlalchemy.orm import Session

from database.models import Video, VideoStat, Hashtag, FashionItem, video_hashtags
from backend.dependencies import get_db
from backend.security import get_current_user

from math import ceil

router = APIRouter(prefix="/api/videos", tags=["Videos"])


def get_latest_stats_subquery(db: Session):
    return (
        db.query(
            VideoStat.video_id.label("video_id"),
            func.max(VideoStat.collected_at).label("latest_at"),
        )
        .group_by(VideoStat.video_id)
        .subquery()
    )


def calculate_video_growth(video_id: int, latest_stat: VideoStat, db: Session):
    if not latest_stat:
        return {
            "view_growth": 0,
            "like_growth": 0,
            "comment_growth": 0,
            "share_growth": 0,
            "trending_score": 0,
            "score_type": "no_stat",
        }

    previous_stat = (
        db.query(VideoStat)
        .filter(
            VideoStat.video_id == video_id,
            VideoStat.collected_at < latest_stat.collected_at,
        )
        .order_by(VideoStat.collected_at.desc())
        .first()
    )

    if previous_stat:
        view_growth = max(0, (latest_stat.view_count or 0) - (previous_stat.view_count or 0))
        like_growth = max(0, (latest_stat.like_count or 0) - (previous_stat.like_count or 0))
        comment_growth = max(0, (latest_stat.comment_count or 0) - (previous_stat.comment_count or 0))
        share_growth = max(0, (latest_stat.share_count or 0) - (previous_stat.share_count or 0))

        trending_score = (
            view_growth * 0.45
            + like_growth * 0.25
            + comment_growth * 0.15
            + share_growth * 0.15
        )
        score_type = "growth_score"
    else:
        view_growth = 0
        like_growth = 0
        comment_growth = 0
        share_growth = 0

        trending_score = (
            (latest_stat.view_count or 0) * 0.5
            + (latest_stat.like_count or 0) * 0.3
            + (latest_stat.comment_count or 0) * 0.1
            + (latest_stat.share_count or 0) * 0.1
        )
        score_type = "fallback_score"

    return {
        "view_growth": int(view_growth),
        "like_growth": int(like_growth),
        "comment_growth": int(comment_growth),
        "share_growth": int(share_growth),
        "trending_score": float(trending_score or 0),
        "score_type": score_type,
    }


def serialize_video(video: Video, stat: VideoStat, db: Session):
    hashtags = (
        db.query(Hashtag.tag_name)
        .join(video_hashtags, Hashtag.hashtag_id == video_hashtags.c.hashtag_id)
        .filter(video_hashtags.c.video_id == video.video_id)
        .all()
    )

    item_rows = (
        db.query(
            FashionItem.item_type,
            func.max(FashionItem.confidence).label("confidence"),
            func.count(FashionItem.item_id).label("count"),
        )
        .filter(FashionItem.video_id == video.video_id)
        .group_by(FashionItem.item_type)
        .order_by(func.count(FashionItem.item_id).desc())
        .all()
    )

    growth_data = calculate_video_growth(video.video_id, stat, db)

    return {
        "video_id": video.video_id,
        "tiktok_video_id": video.tiktok_video_id,
        "description": video.description,
        "video_url": video.video_url,
        "cover_url": video.cover_url,
        "processing_status": video.processing_status,
        "is_analyzed": video.is_analyzed,
        "view_count": stat.view_count if stat else 0,
        "like_count": stat.like_count if stat else 0,
        "comment_count": stat.comment_count if stat else 0,
        "share_count": stat.share_count if stat else 0,
        "view_growth": growth_data["view_growth"],
        "like_growth": growth_data["like_growth"],
        "comment_growth": growth_data["comment_growth"],
        "share_growth": growth_data["share_growth"],
        "trending_score": growth_data["trending_score"],
        "trend_score": growth_data["trending_score"],
        "score_type": growth_data["score_type"],
        "hashtags": [h[0] for h in hashtags],
        "fashion_items": [i.item_type for i in item_rows],
        "fashion_items_detail": [
            {
                "item_type": i.item_type,
                "confidence": float(i.confidence or 0),
                "count": int(i.count or 0),
            }
            for i in item_rows
        ],
        "has_yolo_result": True,
        "has_fashion_items": len(item_rows) > 0,
    }


def build_video_filter_query(
    db: Session,
    latest_stats,
    search: str | None,
    status: str,
    item: str,
):
    """
    Nguồn hiển thị chính: chỉ video đã được pipeline AI xác nhận là hợp lệ.
    Không bắt buộc phải có fashion_items, vì một số video được promote sang success
    theo fashion_relevance_score nhưng chưa có item row đầy đủ.
    """
    query = (
        db.query(Video.video_id.label("video_id"))
        .join(latest_stats, Video.video_id == latest_stats.c.video_id)
        .join(
            VideoStat,
            and_(
                VideoStat.video_id == latest_stats.c.video_id,
                VideoStat.collected_at == latest_stats.c.latest_at,
            ),
        )
        .outerjoin(video_hashtags, video_hashtags.c.video_id == Video.video_id)
        .outerjoin(Hashtag, Hashtag.hashtag_id == video_hashtags.c.hashtag_id)
        .outerjoin(FashionItem, FashionItem.video_id == Video.video_id)
        .filter(Video.is_in_scope == True)
        .filter(Video.processing_status == "success")
        .filter(Video.is_analyzed == True)
    )

    # Frontend chỉ nên gửi all/success. Các trạng thái khác trả rỗng để không lộ dữ liệu rác.
    if status not in ("all", "success"):
        query = query.filter(False)

    if item != "all":
        query = query.filter(FashionItem.item_type == item)

    if search:
        search_like = f"%{search.lower()}%"
        query = query.filter(
            or_(
                func.lower(Video.description).like(search_like),
                func.lower(Hashtag.tag_name).like(search_like),
                func.lower(FashionItem.item_type).like(search_like),
            )
        )

    return query


@router.get("/fashion-items/options")
def get_fashion_item_options(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (
        db.query(FashionItem.item_type)
        .join(Video, Video.video_id == FashionItem.video_id)
        .filter(Video.is_in_scope == True)
        .filter(Video.processing_status == "success")
        .filter(Video.is_analyzed == True)
        .group_by(FashionItem.item_type)
        .order_by(FashionItem.item_type.asc())
        .all()
    )

    return [row[0] for row in rows]


@router.get("/trending")
def get_trending_videos(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: str | None = Query(None),
    status: str = Query("success"),
    item: str = Query("all"),
    sort_by: str = Query("views"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    latest_stats = get_latest_stats_subquery(db)

    filtered_ids_query = build_video_filter_query(
        db=db,
        latest_stats=latest_stats,
        search=search,
        status=status,
        item=item,
    )

    filtered_ids_subquery = filtered_ids_query.distinct().subquery()
    total = db.query(func.count()).select_from(filtered_ids_subquery).scalar() or 0

    if sort_by == "likes":
        order_col = VideoStat.like_count
    elif sort_by == "comments":
        order_col = VideoStat.comment_count
    elif sort_by == "shares":
        order_col = VideoStat.share_count
    elif sort_by == "growth":
        # sẽ sort lại theo view_growth sau serialize
        order_col = VideoStat.view_count
    else:
        order_col = VideoStat.view_count

    page_rows = (
        db.query(
            Video.video_id.label("video_id"),
            order_col.label("sort_value"),
        )
        .join(latest_stats, Video.video_id == latest_stats.c.video_id)
        .join(
            VideoStat,
            and_(
                VideoStat.video_id == latest_stats.c.video_id,
                VideoStat.collected_at == latest_stats.c.latest_at,
            ),
        )
        .join(
            filtered_ids_subquery,
            filtered_ids_subquery.c.video_id == Video.video_id,
        )
        .group_by(Video.video_id, order_col)
        .order_by(desc(order_col))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    page_video_ids = [row.video_id for row in page_rows]

    if not page_video_ids:
        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": ceil(total / page_size) if page_size else 1,
            "items": [],
        }

    rows = (
        db.query(Video, VideoStat)
        .join(latest_stats, Video.video_id == latest_stats.c.video_id)
        .join(
            VideoStat,
            and_(
                VideoStat.video_id == latest_stats.c.video_id,
                VideoStat.collected_at == latest_stats.c.latest_at,
            ),
        )
        .filter(Video.video_id.in_(page_video_ids))
        .filter(Video.is_in_scope == True)
        .filter(Video.processing_status == "success")
        .filter(Video.is_analyzed == True)
        .all()
    )

    row_map = {video.video_id: (video, stat) for video, stat in rows}

    ordered_items = []
    for video_id in page_video_ids:
        if video_id in row_map:
            video, stat = row_map[video_id]
            ordered_items.append(serialize_video(video, stat, db))

    if sort_by == "growth":
        ordered_items.sort(
            key=lambda video: video.get("view_growth") or 0,
            reverse=True,
        )

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": ceil(total / page_size) if page_size else 1,
        "items": ordered_items,
    }


@router.get("/{video_id}/history")
def get_video_history(
    video_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    video = (
        db.query(Video)
        .filter(Video.video_id == video_id)
        .filter(Video.is_in_scope == True)
        .filter(Video.processing_status == "success")
        .filter(Video.is_analyzed == True)
        .first()
    )

    if not video:
        return {
            "video_id": video_id,
            "history": [],
            "trend_status": "unknown",
            "analysis_text": "Không tìm thấy video hợp lệ hoặc video chưa được YOLO/Fashion Filter xác nhận.",
        }

    stats = (
        db.query(VideoStat)
        .filter(VideoStat.video_id == video_id)
        .order_by(VideoStat.collected_at.asc())
        .all()
    )

    history = []
    previous = None

    for stat in stats:
        if previous:
            view_growth = max(0, (stat.view_count or 0) - (previous.view_count or 0))
            like_growth = max(0, (stat.like_count or 0) - (previous.like_count or 0))
            comment_growth = max(0, (stat.comment_count or 0) - (previous.comment_count or 0))
            share_growth = max(0, (stat.share_count or 0) - (previous.share_count or 0))
        else:
            view_growth = 0
            like_growth = 0
            comment_growth = 0
            share_growth = 0

        engagement_rate = (
            ((stat.like_count or 0) + (stat.comment_count or 0) + (stat.share_count or 0))
            / ((stat.view_count or 0) + 1)
        ) * 100

        history.append(
            {
                "collected_at": stat.collected_at,
                "view_count": stat.view_count or 0,
                "like_count": stat.like_count or 0,
                "comment_count": stat.comment_count or 0,
                "share_count": stat.share_count or 0,
                "view_growth": view_growth,
                "like_growth": like_growth,
                "comment_growth": comment_growth,
                "share_growth": share_growth,
                "engagement_rate": engagement_rate,
            }
        )

        previous = stat

    latest_growth = history[-1]["view_growth"] if len(history) >= 2 else 0
    previous_growth = history[-2]["view_growth"] if len(history) >= 3 else 0

    if len(history) < 2:
        trend_status = "not_enough_data"
        analysis_text = "Video chưa có đủ dữ liệu lịch sử để đánh giá xu hướng."
    elif latest_growth > previous_growth and latest_growth > 0:
        trend_status = "increasing"
        analysis_text = "Video đang có xu hướng tăng trưởng, lượt xem mới nhất tăng mạnh hơn kỳ trước."
    elif latest_growth > 0 and latest_growth <= previous_growth:
        trend_status = "slowing"
        analysis_text = "Video vẫn tăng trưởng nhưng tốc độ tăng đang chậm lại."
    else:
        trend_status = "stable"
        analysis_text = "Video gần như không tăng trưởng thêm trong lần cập nhật gần nhất."

    return {
        "video_id": video.video_id,
        "description": video.description,
        "processing_status": video.processing_status,
        "trend_status": trend_status,
        "analysis_text": analysis_text,
        "latest_view_growth": latest_growth,
        "previous_view_growth": previous_growth,
        "history_points": len(history),
        "history": history,
    }
