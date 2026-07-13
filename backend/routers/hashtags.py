from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func, desc, and_
from sqlalchemy.orm import Session

from database.models import (
    Hashtag,
    TrendHistory,
    Video,
    VideoStat,
    FashionItem,
    video_hashtags,
)
from backend.dependencies import get_db
from backend.security import get_current_user
from ai.tag_filters import BLACKLIST_TAGS

from math import ceil

router = APIRouter(prefix="/api/hashtags", tags=["Hashtags"])


@router.get("/trending")
def get_trending_hashtags(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    latest_date = db.query(func.max(TrendHistory.date)).scalar()

    if not latest_date:
        return {
            "items": [],
            "latest_date": None,
            "max_date_in_db": None,
        }

    rows = (
        db.query(
            Hashtag.hashtag_id,
            Hashtag.tag_name,
            TrendHistory.date,
            TrendHistory.view_count,
            TrendHistory.like_count,
            TrendHistory.comment_count,
            TrendHistory.share_count,
            TrendHistory.video_count,
            TrendHistory.engagement_rate,
            TrendHistory.view_growth,
            TrendHistory.like_growth,
            TrendHistory.engagement_growth,
            TrendHistory.trend_score,
        )
        .join(TrendHistory, TrendHistory.hashtag_id == Hashtag.hashtag_id)
        .filter(TrendHistory.date == latest_date)
        .filter(~func.lower(Hashtag.tag_name).in_(list(BLACKLIST_TAGS)))
        .order_by(TrendHistory.trend_score.desc())
        .limit(limit)
        .all()
    )

    items = [
        {
            "hashtag_id": row.hashtag_id,
            "tag_name": row.tag_name,
            "date": row.date,
            "view_count": row.view_count or 0,
            "total_views": row.view_count or 0,
            "like_count": row.like_count or 0,
            "comment_count": row.comment_count or 0,
            "share_count": row.share_count or 0,
            "video_count": row.video_count or 0,
            "total_videos": row.video_count or 0,
            "engagement_rate": row.engagement_rate or 0,
            "view_growth": row.view_growth or 0,
            "like_growth": row.like_growth or 0,
            "engagement_growth": row.engagement_growth or 0,
            "trend_score": row.trend_score or 0,
            "trending_score": row.trend_score or 0,
        }
        for row in rows
    ]

    return {
        "items": items,
        "latest_date": latest_date,
        "max_date_in_db": latest_date,
    }


@router.get("/{hashtag_id}")
def get_hashtag_detail(
    hashtag_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    hashtag = db.query(Hashtag).filter(Hashtag.hashtag_id == hashtag_id).first()

    if not hashtag:
        return {
            "hashtag_id": hashtag_id,
            "tag_name": None,
            "video_count": 0,
            "total_views": 0,
            "trend_score": 0,
            "trending_score": 0,
            "history": [],
        }

    history = (
        db.query(TrendHistory)
        .filter(TrendHistory.hashtag_id == hashtag_id)
        .order_by(TrendHistory.date.asc())
        .all()
    )

    latest_trend = history[-1] if history else None

    real_video_count = (
        db.query(func.count(func.distinct(Video.video_id)))
        .join(video_hashtags, Video.video_id == video_hashtags.c.video_id)
        .filter(video_hashtags.c.hashtag_id == hashtag_id)
        .filter(Video.is_in_scope == True)
        .filter(Video.processing_status == "success")
        .filter(Video.is_analyzed == True)
        .scalar()
        or 0
    )

    return {
        "hashtag_id": hashtag.hashtag_id,
        "tag_name": hashtag.tag_name,
        "category": hashtag.category,
        "video_count": real_video_count,
        "total_views": latest_trend.view_count if latest_trend else 0,
        "trend_score": latest_trend.trend_score if latest_trend else 0,
        "trending_score": latest_trend.trend_score if latest_trend else 0,
        "first_seen": hashtag.first_seen,
        "last_seen": hashtag.last_seen,
        "history": [
            {
                "date": row.date,
                "view_count": row.view_count or 0,
                "like_count": row.like_count or 0,
                "comment_count": row.comment_count or 0,
                "share_count": row.share_count or 0,
                "video_count": row.video_count or 0,
                "engagement_rate": row.engagement_rate or 0,
                "view_growth": row.view_growth or 0,
                "like_growth": row.like_growth or 0,
                "engagement_growth": row.engagement_growth or 0,
                "trend_score": row.trend_score or 0,
                "trending_score": row.trend_score or 0,
                "is_imputed": bool(getattr(row, "is_imputed", False)),
                "data_quality_score": getattr(row, "data_quality_score", 1.0) or 1.0,
            }
            for row in history
        ],
    }


@router.get("/{hashtag_id}/videos")
def get_hashtag_videos(
    hashtag_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    hashtag = db.query(Hashtag).filter(Hashtag.hashtag_id == hashtag_id).first()

    if not hashtag:
        raise HTTPException(status_code=404, detail="Không tìm thấy hashtag")

    latest_trend = (
        db.query(TrendHistory)
        .filter(TrendHistory.hashtag_id == hashtag_id)
        .order_by(TrendHistory.date.desc())
        .first()
    )

    latest_stats = (
        db.query(
            VideoStat.video_id.label("video_id"),
            func.max(VideoStat.collected_at).label("latest_at"),
        )
        .group_by(VideoStat.video_id)
        .subquery()
    )

    eligible_ids_subq = (
        db.query(Video.video_id.label("video_id"))
        .join(video_hashtags, Video.video_id == video_hashtags.c.video_id)
        .join(latest_stats, Video.video_id == latest_stats.c.video_id)
        .filter(video_hashtags.c.hashtag_id == hashtag_id)
        .filter(Video.is_in_scope == True)
        .filter(Video.processing_status == "success")
        .filter(Video.is_analyzed == True)
        .distinct()
        .subquery()
    )

    total = db.query(func.count()).select_from(eligible_ids_subq).scalar() or 0

    sort_view_count = func.max(VideoStat.view_count).label("sort_view_count")

    page_rows = (
        db.query(
            Video.video_id.label("video_id"),
            sort_view_count,
        )
        .join(video_hashtags, Video.video_id == video_hashtags.c.video_id)
        .join(latest_stats, Video.video_id == latest_stats.c.video_id)
        .join(
            VideoStat,
            and_(
                VideoStat.video_id == latest_stats.c.video_id,
                VideoStat.collected_at == latest_stats.c.latest_at,
            ),
        )
        .filter(video_hashtags.c.hashtag_id == hashtag_id)
        .filter(Video.is_in_scope == True)
        .filter(Video.processing_status == "success")
        .filter(Video.is_analyzed == True)
        .group_by(Video.video_id)
        .order_by(desc(sort_view_count))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    page_video_ids = [row.video_id for row in page_rows]

    if not page_video_ids:
        return {
            "hashtag": {
                "hashtag_id": hashtag.hashtag_id,
                "tag_name": hashtag.tag_name,
                "video_count": total,
                "total_views": latest_trend.view_count if latest_trend else 0,
                "trend_score": latest_trend.trend_score if latest_trend else 0,
                "trending_score": latest_trend.trend_score if latest_trend else 0,
            },
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

    ordered_rows = []
    for video_id in page_video_ids:
        if video_id in row_map:
            ordered_rows.append(row_map[video_id])

    items = []

    for video, stat in ordered_rows:
        fashion_items = (
            db.query(FashionItem.item_type)
            .filter(FashionItem.video_id == video.video_id)
            .group_by(FashionItem.item_type)
            .all()
        )

        hashtags = (
            db.query(Hashtag.tag_name)
            .join(video_hashtags, Hashtag.hashtag_id == video_hashtags.c.hashtag_id)
            .filter(video_hashtags.c.video_id == video.video_id)
            .all()
        )

        items.append(
            {
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
                "hashtags": [h[0] for h in hashtags],
                "fashion_items": [item[0] for item in fashion_items],
                "has_yolo_result": True,
                "has_fashion_items": len(fashion_items) > 0,
            }
        )

    return {
        "hashtag": {
            "hashtag_id": hashtag.hashtag_id,
            "tag_name": hashtag.tag_name,
            "video_count": total,
            "total_views": latest_trend.view_count if latest_trend else 0,
            "trend_score": latest_trend.trend_score if latest_trend else 0,
            "trending_score": latest_trend.trend_score if latest_trend else 0,
        },
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": ceil(total / page_size) if page_size else 1,
        "items": items,
    }