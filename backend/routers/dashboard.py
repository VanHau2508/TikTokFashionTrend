from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import (
    Video,
    VideoStat,
    Hashtag,
    TrendHistory,
    Prediction,
    FashionItem,
    CrawlerJob,
    video_hashtags,
)
from backend.dependencies import get_db
from backend.security import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

LSTM_V3_MODEL_VERSION = "lstm_trend_history_growth_v3"


@router.get("/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Dashboard mặc định chỉ thống kê dữ liệu trong phạm vi phân tích chính:
    Video.is_in_scope == True.
    """

    total_raw_videos = db.query(func.count(Video.video_id)).scalar() or 0

    total_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True
    ).scalar() or 0

    out_scope_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == False
    ).scalar() or 0

    success_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "success",
        Video.is_analyzed == True,
    ).scalar() or 0

    failed_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status.in_([
            "failed",
            "failed_no_fashion",
            "failed_no_frame",
            "failed_no_frame_final",
            "error",
        ])
    ).scalar() or 0

    uncertain_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "uncertain"
    ).scalar() or 0

    pending_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "pending"
    ).scalar() or 0

    total_hashtags = (
        db.query(func.count(func.distinct(Hashtag.hashtag_id)))
        .join(video_hashtags, Hashtag.hashtag_id == video_hashtags.c.hashtag_id)
        .join(Video, Video.video_id == video_hashtags.c.video_id)
        .filter(Video.is_in_scope == True)
        .scalar()
        or 0
    )

    total_fashion_items = (
        db.query(func.count(FashionItem.item_id))
        .join(Video, Video.video_id == FashionItem.video_id)
        .filter(Video.is_in_scope == True)
        .filter(Video.processing_status == "success")
        .filter(Video.is_analyzed == True)
        .scalar()
        or 0
    )

    total_predictions = db.query(func.count(Prediction.prediction_id)).filter(
        Prediction.model_version == LSTM_V3_MODEL_VERSION,
        Prediction.prediction_type == "view_growth",
    ).scalar() or 0

    latest_stat_time = (
        db.query(func.max(VideoStat.collected_at))
        .join(Video, Video.video_id == VideoStat.video_id)
        .filter(Video.is_in_scope == True)
        .scalar()
    )

    latest_trend_history_date = db.query(func.max(TrendHistory.date)).scalar()

    latest_prediction_time = db.query(func.max(Prediction.created_at)).filter(
        Prediction.model_version == LSTM_V3_MODEL_VERSION,
        Prediction.prediction_type == "view_growth",
    ).scalar()

    latest_job = db.query(CrawlerJob).order_by(
        CrawlerJob.created_at.desc()
    ).first()

    return {
        "total_videos": total_videos,
        "total_raw_videos": total_raw_videos,
        "out_scope_videos": out_scope_videos,
        "success_videos": success_videos,
        "failed_videos": failed_videos,
        "uncertain_videos": uncertain_videos,
        "pending_videos": pending_videos,
        "total_hashtags": total_hashtags,
        "total_fashion_items": total_fashion_items,
        "total_predictions": total_predictions,
        "latest_stat_time": latest_stat_time,
        "latest_trend_history_date": latest_trend_history_date,
        "latest_prediction_time": latest_prediction_time,
        "prediction_model_version": LSTM_V3_MODEL_VERSION,
        "scope": {
            "default": "in_scope_only",
            "rule": "Video.is_in_scope = true",
            "description": "Dashboard mặc định chỉ hiển thị video thuộc phạm vi phân tích 2026.",
        },
        "latest_crawler_job": {
            "job_id": latest_job.job_id,
            "job_name": latest_job.job_name,
            "job_type": latest_job.job_type,
            "status": latest_job.status,
            "videos_collected": latest_job.videos_collected,
            "created_at": latest_job.created_at,
            "completed_at": latest_job.completed_at
        } if latest_job else None
    }


@router.get("/status-distribution")
def get_status_distribution(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    rows = db.query(
        Video.processing_status,
        func.count(Video.video_id).label("total")
    ).filter(
        Video.is_in_scope == True
    ).group_by(
        Video.processing_status
    ).all()

    return [
        {
            "status": row.processing_status or "unknown",
            "total": row.total
        }
        for row in rows
    ]
