import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, text
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from backend.security import require_admin
from database.models import (
    AIAnalysis,
    AdminTask,
    CrawlerJob,
    FashionItem,
    Hashtag,
    Prediction,
    TikTokUser,
    TrendHistory,
    User,
    Video,
    VideoStat,
)

from .adminTaskCore import (
    DEMO_MODE,
    is_lstm_v3_ready,
    LSTM_V3_CONFIG_PATH,
    LSTM_V3_FEATURE_SCALER_PATH,
    LSTM_V3_MODEL_PATH,
    LSTM_V3_MODEL_VERSION,
    LSTM_V3_TARGET_SCALER_PATH,
    YOLO_MODEL_PATH,
)

router = APIRouter(prefix="/api/admin", tags=["Admin System"])


def json_text(column, key: str):
    """PostgreSQL JSONB ->> helper compatible with SQLAlchemy 2.x."""
    return column.op("->>")(key)


@router.get("/system/data-quality-summary")
def get_data_quality_summary(
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    """
    Admin quality summary theo phạm vi phân tích chính.
    - videos: chỉ tính video is_in_scope=true (2026)
    - raw_total_videos/out_scope_videos: giữ để admin biết dữ liệu thô/lưu trữ
    """
    raw_total_videos = db.query(func.count(Video.video_id)).scalar() or 0

    total_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True
    ).scalar() or 0

    out_scope_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == False
    ).scalar() or 0

    analyzed_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.is_analyzed == True,
    ).scalar() or 0

    pending_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "pending",
    ).scalar() or 0

    yolo_success = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "success",
        Video.is_analyzed == True,
    ).scalar() or 0

    failed_no_fashion = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "failed_no_fashion",
    ).scalar() or 0

    uncertain_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "uncertain",
    ).scalar() or 0

    failed_no_frame = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status.in_(["failed_no_frame", "failed_no_frame_final"]),
    ).scalar() or 0

    error_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "error",
    ).scalar() or 0

    yolo_failed = failed_no_fashion + failed_no_frame + error_videos
    processed_videos = yolo_success + failed_no_fashion + uncertain_videos + failed_no_frame + error_videos

    latest_stat = (
        db.query(VideoStat)
        .join(Video, Video.video_id == VideoStat.video_id)
        .filter(Video.is_in_scope == True)
        .order_by(desc(VideoStat.collected_at))
        .first()
    )

    latest_history = db.query(TrendHistory).order_by(
        desc(TrendHistory.date)
    ).first()

    latest_prediction = db.query(Prediction).filter(
        Prediction.model_version == LSTM_V3_MODEL_VERSION,
        Prediction.prediction_type == "view_growth",
    ).order_by(
        desc(Prediction.created_at)
    ).first()

    fashion_items = (
        db.query(func.count(FashionItem.item_id))
        .join(Video, Video.video_id == FashionItem.video_id)
        .filter(Video.is_in_scope == True)
        .filter(Video.processing_status == "success")
        .scalar()
        or 0
    )

    return {
        "users": db.query(func.count(User.user_id)).scalar() or 0,
        "tiktok_users": db.query(func.count(TikTokUser.tiktok_user_id)).scalar() or 0,
        "raw_total_videos": raw_total_videos,
        "out_scope_videos": out_scope_videos,
        "videos": total_videos,
        "analyzed_videos": analyzed_videos,
        "pending_videos": pending_videos,
        "processed_videos": processed_videos,
        "hashtags": db.query(func.count(Hashtag.hashtag_id)).scalar() or 0,
        "video_stats": db.query(func.count(VideoStat.stat_id)).scalar() or 0,
        "fashion_items": fashion_items,
        "ai_analysis": db.query(func.count(AIAnalysis.analysis_id)).scalar() or 0,
        "trend_history": db.query(func.count(TrendHistory.history_id)).scalar() or 0,
        "predictions": db.query(func.count(Prediction.prediction_id)).filter(
            Prediction.model_version == LSTM_V3_MODEL_VERSION,
            Prediction.prediction_type == "view_growth",
        ).scalar() or 0,
        "crawler_jobs": db.query(func.count(CrawlerJob.job_id)).scalar() or 0,
        "admin_tasks": db.query(func.count(AdminTask.task_id)).scalar() or 0,
        "yolo_success": yolo_success,
        "yolo_failed": yolo_failed,
        "failed_no_fashion": failed_no_fashion,
        "uncertain_videos": uncertain_videos,
        "failed_no_frame": failed_no_frame,
        "error_videos": error_videos,
        "yolo_success_rate": round((yolo_success / total_videos) * 100, 2) if total_videos else 0,
        "processed_success_rate": round((yolo_success / processed_videos) * 100, 2) if processed_videos else 0,
        "latest": {
            "latest_video_stat_at": latest_stat.collected_at if latest_stat else None,
            "latest_trend_history_date": latest_history.date if latest_history else None,
            "latest_prediction_at": latest_prediction.created_at if latest_prediction else None,
        },
        "demo_mode": DEMO_MODE,
    }


@router.get("/system/model-evaluation")
def get_model_evaluation(
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    """
    Tách rõ metric YOLO item confidence và fashion relevance score.
    Không tính video out_scope vào đánh giá mô hình chính.
    """
    total_in_scope = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True
    ).scalar() or 0

    yolo_success = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "success",
        Video.is_analyzed == True,
    ).scalar() or 0

    failed_no_fashion = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "failed_no_fashion",
    ).scalar() or 0

    uncertain = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "uncertain",
    ).scalar() or 0

    failed_no_frame = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status.in_(["failed_no_frame", "failed_no_frame_final"]),
    ).scalar() or 0

    error = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "error",
    ).scalar() or 0

    pending = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "pending",
    ).scalar() or 0

    processed = yolo_success + failed_no_fashion + uncertain + failed_no_frame + error
    fashion_evaluable = yolo_success + failed_no_fashion + uncertain
    failed_count = failed_no_fashion + failed_no_frame + error

    avg_yolo_item_confidence = db.query(
        func.avg(FashionItem.confidence)
    ).join(
        Video, Video.video_id == FashionItem.video_id
    ).filter(
        Video.is_in_scope == True,
        Video.processing_status == "success",
        FashionItem.confidence.isnot(None),
    ).scalar()

    latest_ai_ids = (
        db.query(
            AIAnalysis.video_id.label("video_id"),
            func.max(AIAnalysis.analysis_id).label("latest_analysis_id"),
        )
        .join(Video, Video.video_id == AIAnalysis.video_id)
        .filter(Video.is_in_scope == True)
        .filter(AIAnalysis.analysis_type == "vision")
        .filter(json_text(AIAnalysis.result_json, "result_kind") == "fashion_relevance")
        .group_by(AIAnalysis.video_id)
        .subquery()
    )

    avg_relevance_confidence = db.query(
        func.avg(AIAnalysis.confidence_score)
    ).join(
        latest_ai_ids,
        AIAnalysis.analysis_id == latest_ai_ids.c.latest_analysis_id,
    ).filter(
        AIAnalysis.confidence_score.isnot(None)
    ).scalar()

    total_analysis = db.query(func.count(AIAnalysis.analysis_id)).join(
        Video, Video.video_id == AIAnalysis.video_id
    ).filter(
        Video.is_in_scope == True,
        AIAnalysis.analysis_type == "vision",
        json_text(AIAnalysis.result_json, "result_kind") == "fashion_relevance",
    ).scalar() or 0

    total_predictions = db.query(func.count(Prediction.prediction_id)).filter(
        Prediction.model_version == LSTM_V3_MODEL_VERSION,
        Prediction.prediction_type == "view_growth",
    ).scalar() or 0

    evaluated_predictions = db.query(func.count(Prediction.prediction_id)).filter(
        Prediction.model_version == LSTM_V3_MODEL_VERSION,
        Prediction.prediction_type == "view_growth",
        Prediction.actual_value.isnot(None),
    ).scalar() or 0

    avg_accuracy = db.query(
        func.avg(Prediction.accuracy_score)
    ).filter(
        Prediction.model_version == LSTM_V3_MODEL_VERSION,
        Prediction.prediction_type == "view_growth",
        Prediction.accuracy_score.isnot(None),
    ).scalar()

    return {
        "yolo": {
            "model_name": "YOLOv8m Fashion Detection",
            "total_in_scope": total_in_scope,
            "success_count": yolo_success,
            "failed_count": failed_count,
            "failed_no_fashion": failed_no_fashion,
            "uncertain": uncertain,
            "failed_no_frame": failed_no_frame,
            "error": error,
            "pending": pending,
            "processed_count": processed,
            "pipeline_success_rate": round((yolo_success / total_in_scope) * 100, 2) if total_in_scope else 0,
            "processed_success_rate": round((yolo_success / processed) * 100, 2) if processed else 0,
            "fashion_detection_rate": round((yolo_success / fashion_evaluable) * 100, 2) if fashion_evaluable else 0,
            "technical_failure_rate": round((failed_no_frame / processed) * 100, 2) if processed else 0,
            "average_yolo_item_confidence": round(float(avg_yolo_item_confidence or 0), 4),
            "average_relevance_confidence": round(float(avg_relevance_confidence or 0), 4),
            # Legacy fields giữ để frontend cũ không lỗi.
            "success_rate": round((yolo_success / total_in_scope) * 100, 2) if total_in_scope else 0,
            "average_confidence": round(float(avg_yolo_item_confidence or 0), 4),
            "total_analysis": total_analysis,
        },
        "lstm": {
            "model_name": "LSTM v3 Trend Prediction",
            "model_version": LSTM_V3_MODEL_VERSION,
            "total_predictions": total_predictions,
            "evaluated_predictions": evaluated_predictions,
            "pending_evaluation": max(0, total_predictions - evaluated_predictions),
            "average_accuracy": round(float(avg_accuracy or 0), 4),
            "evaluation_note": (
                "Chưa có actual_value vì cần trend_history của predicted_for_date. "
                "Hãy chạy Evaluate Predictions sau khi đã sync stats và build trend_history cho ngày dự đoán."
                if evaluated_predictions == 0 else None
            ),
        },
    }


@router.get("/system/pipeline-status")
def get_pipeline_status(
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    pipeline_definitions = [
        ("crawl_hashtags", "Thu thập video TikTok", "Lấy video theo danh sách hashtag thời trang"),
        ("process_yolo", "Nhận diện thời trang bằng YOLOv8", "Lọc video thời trang và nhận diện item nếu có"),
        ("sync_stats", "Đồng bộ chỉ số video", "Cập nhật lượt xem, thích, bình luận và chia sẻ"),
        ("build_trend_history", "Tạo lịch sử xu hướng", "Tổng hợp dữ liệu hashtag theo ngày cho LSTM"),
        ("run_prediction", "Dự đoán xu hướng bằng LSTM v3", "Dự đoán view_growth ngày tiếp theo theo hashtag"),
        ("evaluate_predictions", "Đánh giá dự đoán", "Cập nhật actual_value và accuracy_score cho predictions"),
        ("backup_database", "Sao lưu cơ sở dữ liệu", "Xuất file backup PostgreSQL"),
    ]

    pipeline = []

    for task_type, title, description in pipeline_definitions:
        latest_task = db.query(AdminTask).filter(
            AdminTask.task_type == task_type
        ).order_by(
            desc(AdminTask.created_at)
        ).first()

        pipeline.append({
            "task_type": task_type,
            "title": latest_task.title if latest_task else title,
            "description": description,
            "status": latest_task.status if latest_task else "not_run",
            "started_at": latest_task.started_at if latest_task else None,
            "completed_at": latest_task.completed_at if latest_task else None,
            "error_message": latest_task.error_message if latest_task else None,
            "result": latest_task.result if latest_task else None,
        })

    return {
        "pipeline": pipeline,
        "demo_mode": DEMO_MODE,
    }


@router.get("/control-center")
def get_admin_control_center(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    total_users = db.query(func.count(User.user_id)).scalar() or 0

    verified_users = db.query(func.count(User.user_id)).filter(
        User.is_email_verified == True
    ).scalar() or 0

    active_users = db.query(func.count(User.user_id)).filter(
        User.is_active == True
    ).scalar() or 0

    raw_total_videos = db.query(func.count(Video.video_id)).scalar() or 0

    total_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True
    ).scalar() or 0

    out_scope_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == False
    ).scalar() or 0

    yolo_success = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "success",
        Video.is_analyzed == True,
    ).scalar() or 0

    total_hashtags = db.query(func.count(Hashtag.hashtag_id)).scalar() or 0

    total_items = (
        db.query(func.count(FashionItem.item_id))
        .join(Video, Video.video_id == FashionItem.video_id)
        .filter(Video.is_in_scope == True)
        .filter(Video.processing_status == "success")
        .scalar()
        or 0
    )

    total_predictions = db.query(func.count(Prediction.prediction_id)).filter(
        Prediction.model_version == LSTM_V3_MODEL_VERSION,
        Prediction.prediction_type == "view_growth",
    ).scalar() or 0

    jobs_total = db.query(func.count(CrawlerJob.job_id)).scalar() or 0

    jobs_completed = db.query(func.count(CrawlerJob.job_id)).filter(
        CrawlerJob.status == "completed"
    ).scalar() or 0

    jobs_failed = db.query(func.count(CrawlerJob.job_id)).filter(
        CrawlerJob.status == "failed"
    ).scalar() or 0

    latest_stat = (
        db.query(VideoStat)
        .join(Video, Video.video_id == VideoStat.video_id)
        .filter(Video.is_in_scope == True)
        .order_by(desc(VideoStat.collected_at))
        .first()
    )

    latest_prediction = db.query(Prediction).filter(
        Prediction.model_version == LSTM_V3_MODEL_VERSION,
        Prediction.prediction_type == "view_growth",
    ).order_by(
        desc(Prediction.created_at)
    ).first()

    latest_job = db.query(CrawlerJob).order_by(
        desc(CrawlerJob.created_at)
    ).first()

    return {
        "summary": {
            "total_users": total_users,
            "verified_users": verified_users,
            "active_users": active_users,
            "raw_total_videos": raw_total_videos,
            "out_scope_videos": out_scope_videos,
            "total_videos": total_videos,
            "yolo_success": yolo_success,
            "total_hashtags": total_hashtags,
            "total_items": total_items,
            "total_predictions": total_predictions,
            "jobs_total": jobs_total,
            "jobs_completed": jobs_completed,
            "jobs_failed": jobs_failed,
        },
        "latest": {
            "latest_video_stat_at": latest_stat.collected_at if latest_stat else None,
            "latest_prediction_at": latest_prediction.created_at if latest_prediction else None,
            "latest_job_name": latest_job.job_name if latest_job else None,
            "latest_job_status": latest_job.status if latest_job else None,
            "latest_job_at": latest_job.created_at if latest_job else None,
        },
        "health": {
            "database": "connected",
            "crawler": "ready",
            "yolo": "ready" if os.path.exists(YOLO_MODEL_PATH) else "missing_model",
            "lstm": "ready" if is_lstm_v3_ready() else "missing_model",
            "smtp": "enabled" if os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD") else "not_configured",
        },
    }


@router.get("/system-health")
def get_system_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    database_status = "connected"

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    model_files = {
        "yolo_model": {
            "label": "YOLOv8m nhận diện thời trang",
            "path": YOLO_MODEL_PATH,
            "exists": os.path.exists(YOLO_MODEL_PATH),
        },
        "lstm_model": {
            "label": "LSTM v3 dự đoán xu hướng",
            "path": LSTM_V3_MODEL_PATH,
            "exists": os.path.exists(LSTM_V3_MODEL_PATH),
        },
        "feature_scaler": {
            "label": "Bộ chuẩn hóa feature LSTM v3",
            "path": LSTM_V3_FEATURE_SCALER_PATH,
            "exists": os.path.exists(LSTM_V3_FEATURE_SCALER_PATH),
        },
        "target_scaler": {
            "label": "Bộ chuẩn hóa target LSTM v3",
            "path": LSTM_V3_TARGET_SCALER_PATH,
            "exists": os.path.exists(LSTM_V3_TARGET_SCALER_PATH),
        },
        "lstm_config": {
            "label": "Cấu hình LSTM v3",
            "path": LSTM_V3_CONFIG_PATH,
            "exists": os.path.exists(LSTM_V3_CONFIG_PATH),
        },
    }

    smtp_enabled = bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))

    return {
        "database": database_status,
        "smtp": "enabled" if smtp_enabled else "not_configured",
        "dev_mode_show_otp": os.getenv("DEV_MODE_SHOW_OTP", "false"),
        "model_files": model_files,
        "server_time": datetime.now(timezone.utc),
    }
