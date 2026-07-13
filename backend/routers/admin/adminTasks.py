from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from backend.security import require_admin
from database.config import SessionLocal
from database.models import AdminTask

from .adminTaskCore import (
    ADMIN_TASKS,
    MAX_ADMIN_TASK_HISTORY,
    apply_demo_limits,
    BackupDatabaseTaskRequest,
    BuildTrendHistoryTaskRequest,
    CrawlHashtagsTaskRequest,
    create_admin_task,
    EvaluatePredictionsTaskRequest,
    is_task_cancel_requested,
    payload_to_dict,
    PredictionTaskRequest,
    run_admin_background_task,
    run_backup_database_job,
    run_build_trend_history_job,
    run_crawl_hashtags_job,
    run_evaluate_predictions_job,
    run_lstm_prediction_job,
    run_sync_stats_job,
    run_yolo_process_job,
    serialize_admin_task,
    SyncStatsTaskRequest,
    YoloProcessTaskRequest,
)

router = APIRouter(prefix="/api/admin", tags=["Admin Tasks"])


@router.get("/tasks/history")
def get_admin_task_history(
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    """
    Lấy lịch sử task từ DB. Nếu DB chưa có admin_tasks thì fallback về RAM.
    """
    try:
        db_tasks = db.query(AdminTask).order_by(
            desc(AdminTask.created_at)
        ).limit(MAX_ADMIN_TASK_HISTORY).all()

        if db_tasks:
            return {
                "items": [serialize_admin_task(task) for task in db_tasks]
            }

    except Exception:
        pass

    items = sorted(
        ADMIN_TASKS.values(),
        key=lambda item: item.get("created_at") or "",
        reverse=True,
    )

    return {
        "items": items[:MAX_ADMIN_TASK_HISTORY]
    }


# Alias giữ tương thích với controller cũ nếu đang gọi /tasks/history-db
@router.get("/tasks/history-db")
def get_admin_task_history_db(
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    return get_admin_task_history(db=db, current_admin=current_admin)


@router.get("/tasks/{task_id}")
def get_admin_task_detail(
    task_id: str,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    if task_id.isdigit():
        db_task = db.query(AdminTask).filter(AdminTask.task_id == int(task_id)).first()

        if db_task:
            return serialize_admin_task(db_task)

    task = ADMIN_TASKS.get(task_id)

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy task.",
        )

    return task


@router.post("/tasks/crawl-hashtags")
def task_crawl_hashtags(
    payload: CrawlHashtagsTaskRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(require_admin),
):
    hashtags = [
        item.strip().replace("#", "")
        for item in payload.hashtags
        if item and item.strip()
    ]

    if not hashtags:
        raise HTTPException(
            status_code=400,
            detail="Vui lòng nhập ít nhất một hashtag.",
        )

    if payload.max_videos <= 0 or payload.max_videos > 3000:
        raise HTTPException(
            status_code=400,
            detail="max_videos phải nằm trong khoảng 1 đến 3000.",
        )

    if payload.max_scrolls <= 0 or payload.max_scrolls > 300:
        raise HTTPException(
            status_code=400,
            detail="max_scrolls phải nằm trong khoảng 1 đến 300.",
        )

    parameters = payload_to_dict(payload)
    parameters["hashtags"] = hashtags
    parameters = apply_demo_limits("crawl_hashtags", parameters)

    task = create_admin_task(
        task_type="crawl_hashtags",
        title="Crawl TikTok Hashtags",
        parameters=parameters,
    )

    background_tasks.add_task(
        run_admin_background_task,
        task["task_id"],
        run_crawl_hashtags_job,
        parameters,
    )

    return {
        "message": "Đã bắt đầu crawl hashtags.",
        "task": task,
    }


@router.post("/tasks/process-yolo")
def task_process_yolo(
    payload: YoloProcessTaskRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(require_admin),
):
    if payload.batch_size <= 0 or payload.batch_size > 200:
        raise HTTPException(
            status_code=400,
            detail="batch_size phải nằm trong khoảng 1 đến 200.",
        )

    if payload.confidence <= 0 or payload.confidence >= 1:
        raise HTTPException(
            status_code=400,
            detail="confidence phải nằm trong khoảng 0 đến 1.",
        )

    parameters = payload_to_dict(payload)
    parameters = apply_demo_limits("process_yolo", parameters)

    task = create_admin_task(
        task_type="process_yolo",
        title="YOLOv8 Fashion Detection",
        parameters=parameters,
    )

    background_tasks.add_task(
        run_admin_background_task,
        task["task_id"],
        run_yolo_process_job,
        parameters,
    )

    return {
        "message": "Đã bắt đầu xử lý YOLOv8.",
        "task": task,
    }


@router.post("/tasks/sync-stats")
def task_sync_stats(
    payload: SyncStatsTaskRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(require_admin),
):
    if payload.hours_gap <= 0 or payload.hours_gap > 720:
        raise HTTPException(
            status_code=400,
            detail="hours_gap phải nằm trong khoảng 1 đến 720.",
        )

    if payload.limit <= 0 or payload.limit > 20000:
        raise HTTPException(
            status_code=400,
            detail="limit phải nằm trong khoảng 1 đến 20000.",
        )

    parameters = payload_to_dict(payload)
    parameters = apply_demo_limits("sync_stats", parameters)

    task = create_admin_task(
        task_type="sync_stats",
        title="Sync Video Stats",
        parameters=parameters,
    )

    background_tasks.add_task(
        run_admin_background_task,
        task["task_id"],
        run_sync_stats_job,
        parameters,
    )

    return {
        "message": "Đã bắt đầu sync video_stats.",
        "task": task,
    }


@router.post("/tasks/build-trend-history")
def task_build_trend_history(
    payload: BuildTrendHistoryTaskRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(require_admin),
):
    if not payload.start_date or not payload.end_date:
        raise HTTPException(
            status_code=400,
            detail="Vui lòng nhập start_date và end_date.",
        )

    if payload.min_distinct_stat_days <= 0 or payload.min_distinct_stat_days > 30:
        raise HTTPException(
            status_code=400,
            detail="min_distinct_stat_days phải nằm trong khoảng 1 đến 30.",
        )

    parameters = payload_to_dict(payload)

    task = create_admin_task(
        task_type="build_trend_history",
        title="Build Trend History",
        parameters=parameters,
    )

    background_tasks.add_task(
        run_admin_background_task,
        task["task_id"],
        run_build_trend_history_job,
        parameters,
    )

    return {
        "message": "Đã bắt đầu build trend_history.",
        "task": task,
    }


@router.post("/tasks/run-prediction")
def task_run_prediction(
    payload: PredictionTaskRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(require_admin),
):
    parameters = payload_to_dict(payload)
    parameters = apply_demo_limits("run_prediction", parameters)

    if parameters.get("limit") is not None and int(parameters["limit"]) <= 0:
        raise HTTPException(
            status_code=400,
            detail="limit phải lớn hơn 0 hoặc để trống.",
        )

    task = create_admin_task(
        task_type="run_prediction",
        title="Run LSTM Prediction",
        parameters=parameters,
    )

    background_tasks.add_task(
        run_admin_background_task,
        task["task_id"],
        run_lstm_prediction_job,
        parameters,
    )

    return {
        "message": "Đã bắt đầu chạy LSTM prediction.",
        "task": task,
    }


@router.post("/tasks/evaluate-predictions")
def task_evaluate_predictions(
    payload: EvaluatePredictionsTaskRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(require_admin),
):
    parameters = payload_to_dict(payload)
    parameters = apply_demo_limits("evaluate_predictions", parameters)

    if parameters.get("limit") is not None and int(parameters["limit"]) <= 0:
        raise HTTPException(
            status_code=400,
            detail="limit phải lớn hơn 0 hoặc để trống.",
        )

    task = create_admin_task(
        task_type="evaluate_predictions",
        title="Evaluate LSTM Predictions",
        parameters=parameters,
    )

    background_tasks.add_task(
        run_admin_background_task,
        task["task_id"],
        run_evaluate_predictions_job,
        parameters,
    )

    return {
        "message": "Đã bắt đầu đánh giá kết quả dự đoán.",
        "task": task,
    }


@router.post("/tasks/backup-database")
def task_backup_database(
    payload: BackupDatabaseTaskRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(require_admin),
):
    parameters = payload_to_dict(payload)

    task = create_admin_task(
        task_type="backup_database",
        title="Backup Database",
        parameters=parameters,
    )

    background_tasks.add_task(
        run_admin_background_task,
        task["task_id"],
        run_backup_database_job,
        parameters,
    )

    return {
        "message": "Đã bắt đầu backup database.",
        "task": task,
    }


@router.post("/tasks/{task_id}/cancel")
def cancel_admin_task(
    task_id: int,
    current_admin=Depends(require_admin),
):
    db = SessionLocal()

    try:
        task = db.query(AdminTask).filter(AdminTask.task_id == task_id).first()

        if not task:
            raise HTTPException(status_code=404, detail="Không tìm thấy task.")

        if task.status not in ["pending", "queued", "running"]:
            return {
                "message": "Task này đã hoàn tất hoặc không thể dừng.",
                "task_id": task_id,
                "status": task.status,
            }

        task.status = "cancel_requested"

        logs = task.logs or []
        logs.append({
            "time": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "message": "Admin đã yêu cầu dừng tác vụ.",
        })

        task.logs = logs
        db.commit()

        return {
            "message": "Đã gửi yêu cầu dừng task.",
            "task_id": task_id,
            "status": "cancel_requested",
        }

    finally:
        db.close()
