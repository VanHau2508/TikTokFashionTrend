import os
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import func, desc, or_, text
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from pydantic import BaseModel, EmailStr
from backend.dependencies import get_db
from backend.security import require_admin, hash_password
import subprocess
import sys
from pathlib import Path
import asyncio
import shutil
import time
from uuid import uuid4
from typing import Any

from crawler.sync_video_stats import VideoStatsSyncer
from database.config import SessionLocal
from database.models import (
    User,
    Role,
    TikTokUser,
    Video,
    VideoStat,
    Hashtag,
    FashionItem,
    AIAnalysis,
    TrendHistory,
    Prediction,
    CrawlerJob,
    AdminTask
)

router = APIRouter(prefix="/api/admin", tags=["Admin"])

LSTM_V3_MODEL_VERSION = "lstm_trend_history_growth_v3"

YOLO_MODEL_PATH = "ai/models/yolov8m_fashion_best.pt"

LSTM_V3_MODEL_DIR = "ai/models/lstm_trend_history_v3"
LSTM_V3_MODEL_PATH = f"{LSTM_V3_MODEL_DIR}/lstm_trend_history_growth_model_v3.keras"
LSTM_V3_FEATURE_SCALER_PATH = f"{LSTM_V3_MODEL_DIR}/trend_history_feature_scaler_v3.pkl"
LSTM_V3_TARGET_SCALER_PATH = f"{LSTM_V3_MODEL_DIR}/trend_history_target_scaler_v3.pkl"
LSTM_V3_CONFIG_PATH = f"{LSTM_V3_MODEL_DIR}/lstm_trend_history_growth_config_v3.json"


def is_lstm_v3_ready():
    return (
        os.path.exists(LSTM_V3_MODEL_PATH)
        and os.path.exists(LSTM_V3_FEATURE_SCALER_PATH)
        and os.path.exists(LSTM_V3_TARGET_SCALER_PATH)
        and os.path.exists(LSTM_V3_CONFIG_PATH)
    )

# ============================================================
# DEMO MODE
# ============================================================
# Khi bảo vệ/demo, bật DEMO_MODE=true trong .env để giới hạn tác vụ nặng.
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"


def apply_demo_limits(task_type: str, parameters: dict[str, Any]):
    """
    Giới hạn tham số khi demo để hệ thống chạy nhanh, ổn định và ít lỗi hơn.
    Không làm thay đổi logic chính, chỉ clamp các giá trị đầu vào.
    """
    if not DEMO_MODE:
        return parameters

    parameters = dict(parameters)

    if task_type == "crawl_hashtags":
        parameters["max_videos"] = min(int(parameters.get("max_videos") or 10), 10)
        parameters["max_scrolls"] = min(int(parameters.get("max_scrolls") or 1), 1)

    elif task_type == "process_yolo":
        parameters["batch_size"] = min(int(parameters.get("batch_size") or 5), 5)
        parameters["confidence"] = float(parameters.get("confidence") or 0.4)

    elif task_type == "sync_stats":
        parameters["limit"] = min(int(parameters.get("limit") or 5), 5)
        parameters["hours_gap"] = int(parameters.get("hours_gap") or 1)

    elif task_type == "run_prediction":
        raw_limit = parameters.get("limit")
        if raw_limit in [None, "", 0, "0"]:
            parameters["limit"] = 20
        else:
            parameters["limit"] = min(int(raw_limit), 20)

    elif task_type == "evaluate_predictions":
        raw_limit = parameters.get("limit")
        if raw_limit in [None, "", 0, "0"]:
            parameters["limit"] = 100
        else:
            parameters["limit"] = min(int(raw_limit), 100)

    return parameters


class AdminCreateUserRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str | None = None
    role_name: str = "user"
    is_active: bool = True
    is_email_verified: bool = True


class AdminUpdateUserRequest(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    full_name: str | None = None
    avatar_url: str | None = None
    role_name: str | None = None
    is_active: bool | None = None
    is_email_verified: bool | None = None

class CrawlHashtagsTaskRequest(BaseModel):
    hashtags: list[str]
    max_videos: int = 300
    max_scrolls: int = 30
    cookies_file: str = "cookies.json"


class YoloProcessTaskRequest(BaseModel):
    batch_size: int = 20
    confidence: float = 0.4
    model_path: str = "ai/models/yolov8m_fashion_best.pt"


class SyncStatsTaskRequest(BaseModel):
    hours_gap: int = 16
    limit: int = 2500


class BuildTrendHistoryTaskRequest(BaseModel):
    start_date: str
    end_date: str
    min_distinct_stat_days: int = 4
    clean_before_build: bool = False


class PredictionTaskRequest(BaseModel):
    limit: int | None = None


class EvaluatePredictionsTaskRequest(BaseModel):
    limit: int | None = 500


class BackupDatabaseTaskRequest(BaseModel):
    file_prefix: str = "backup"
    timeout_seconds: int = 300


class AdminUserStatusRequest(BaseModel):
    is_active: bool

def admin_serialize_user(user: User, role: Role | None = None):
    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "avatar_url": getattr(user, "avatar_url", None),
        "role": role.role_name if role else None,
        "role_id": user.role_id,
        "is_active": user.is_active,
        "is_email_verified": getattr(user, "is_email_verified", False),
        "created_at": user.created_at,
        "updated_at": getattr(user, "updated_at", None),
        "last_login": user.last_login,
    }

SUPER_ADMIN_USERNAME = "admin123"


def get_user_role_name(db: Session, user: User) -> str:
    role = db.query(Role).filter(Role.role_id == user.role_id).first()
    return role.role_name.lower() if role and role.role_name else "user"


def is_super_admin(user: User) -> bool:
    return user.username == SUPER_ADMIN_USERNAME


def is_target_super_admin(user: User) -> bool:
    return user.username == SUPER_ADMIN_USERNAME


def ensure_can_manage_user(
    db: Session,
    current_user: User,
    target_user: User,
    action: str = "manage"
):
    """
    Super Admin admin123:
    - quản lý được admin khác và user
    - nhưng bản thân admin123 không được sửa/khóa

    Admin thường:
    - chỉ quản lý được user thường
    - không quản lý được admin khác
    """

    if is_target_super_admin(target_user):
        raise HTTPException(
            status_code=403,
            detail="Tài khoản Super Admin admin123 không thể bị chỉnh sửa hoặc khóa."
        )

    current_role = get_user_role_name(db, current_user)
    target_role = get_user_role_name(db, target_user)

    if current_role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền quản trị."
        )

    if is_super_admin(current_user):
        return True

    if target_role == "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin thường không được chỉnh sửa hoặc khóa tài khoản admin khác."
        )

    return True


def ensure_can_assign_role(
    db: Session,
    current_user: User,
    role_name: str
):
    """
    Chỉ Super Admin admin123 mới được tạo/cấp quyền admin.
    Admin thường chỉ được tạo/cấp quyền user.
    """

    role_name = (role_name or "user").lower()

    if role_name == "admin" and not is_super_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Chỉ Super Admin admin123 mới được cấp quyền admin."
        )

    return True

@router.post("/users")
def admin_create_user(
    payload: AdminCreateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    ensure_can_assign_role(db, current_user, payload.role_name)

    existing_user = db.query(User).filter(
        or_(
            User.username == payload.username,
            User.email == payload.email
        )
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username hoặc email đã tồn tại"
        )

    role = db.query(Role).filter(Role.role_name == payload.role_name).first()

    if not role:
        raise HTTPException(
            status_code=400,
            detail="Role không tồn tại"
        )

    now = datetime.now(timezone.utc)

    new_user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role_id=role.role_id,
        is_active=payload.is_active,
        is_email_verified=payload.is_email_verified,
        email_verified_at=now if payload.is_email_verified else None,
        created_at=now,
        updated_at=now,
        last_login=now
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "Tạo tài khoản thành công",
        "user": admin_serialize_user(new_user, role)
    }

def get_user_role_name(db: Session, user: User) -> str:
    role = db.query(Role).filter(Role.role_id == user.role_id).first()
    return role.role_name.lower() if role and role.role_name else "user"


def is_super_admin(user: User) -> bool:
    return user.username == SUPER_ADMIN_USERNAME


def is_target_super_admin(user: User) -> bool:
    return user.username == SUPER_ADMIN_USERNAME


def ensure_can_manage_user(
    db: Session,
    current_user: User,
    target_user: User,
    action: str = "manage"
):
    """
    Super Admin admin123:
    - quản lý được admin khác và user
    - nhưng bản thân admin123 không được sửa/khóa

    Admin thường:
    - chỉ quản lý được user thường
    - không quản lý được admin khác
    """

    if is_target_super_admin(target_user):
        raise HTTPException(
            status_code=403,
            detail="Tài khoản Super Admin admin123 không thể bị chỉnh sửa hoặc khóa."
        )

    current_role = get_user_role_name(db, current_user)
    target_role = get_user_role_name(db, target_user)

    if current_role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền quản trị."
        )

    if is_super_admin(current_user):
        return True

    if target_role == "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin thường không được chỉnh sửa hoặc khóa tài khoản admin khác."
        )

    return True


def ensure_can_assign_role(
    db: Session,
    current_user: User,
    role_name: str
):
    """
    Chỉ Super Admin admin123 mới được tạo/cấp quyền admin.
    Admin thường chỉ được tạo/cấp quyền user.
    """

    role_name = (role_name or "user").lower()

    if role_name == "admin" and not is_super_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Chỉ Super Admin admin123 mới được cấp quyền admin."
        )

    return True


@router.get("/crawler-jobs")
def get_crawler_jobs(
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin)
):
    jobs = db.query(CrawlerJob).order_by(
        CrawlerJob.created_at.desc()
    ).limit(50).all()

    return [
        {
            "job_id": job.job_id,
            "job_name": job.job_name,
            "job_type": job.job_type,
            "status": job.status,
            "videos_collected": job.videos_collected,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "error_message": job.error_message,
            "created_at": job.created_at
        }
        for job in jobs
    ]

@router.put("/users/{user_id}")
def admin_update_user(
    user_id: int,
    payload: AdminUpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    user = db.query(User).filter(User.user_id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy user"
        )

    ensure_can_manage_user(db, current_user, user, action="update")

    if payload.username and payload.username != user.username:
        existing = db.query(User).filter(User.username == payload.username).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Username đã tồn tại"
            )

        user.username = payload.username

    if payload.email and payload.email != user.email:
        existing = db.query(User).filter(User.email == payload.email).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Email đã tồn tại"
            )

        user.email = payload.email

    if payload.full_name is not None:
        user.full_name = payload.full_name

    if hasattr(user, "avatar_url") and payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url

    if payload.role_name:
        ensure_can_assign_role(db, current_user, payload.role_name)

        role = db.query(Role).filter(Role.role_name == payload.role_name).first()

        if not role:
            raise HTTPException(
                status_code=400,
                detail="Role không tồn tại"
            )

        user.role_id = role.role_id

    if payload.is_active is not None:
        if user.user_id == current_user.user_id and payload.is_active is False:
            raise HTTPException(
                status_code=400,
                detail="Bạn không thể tự khóa tài khoản của chính mình"
            )

        user.is_active = payload.is_active

    if payload.is_email_verified is not None:
        user.is_email_verified = payload.is_email_verified
        user.email_verified_at = (
            datetime.now(timezone.utc)
            if payload.is_email_verified
            else None
        )

    if hasattr(user, "updated_at"):
        user.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user)

    role = db.query(Role).filter(Role.role_id == user.role_id).first()

    return {
        "message": "Cập nhật user thành công",
        "user": admin_serialize_user(user, role)
    }

@router.patch("/users/{user_id}/status")
def admin_update_user_status(
    user_id: int,
    payload: AdminUserStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    user = db.query(User).filter(User.user_id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy user"
        )

    if user.user_id == current_user.user_id:
        raise HTTPException(
            status_code=400,
            detail="Bạn không thể tự khóa tài khoản của chính mình"
        )

    ensure_can_manage_user(db, current_user, user, action="status")

    user.is_active = payload.is_active

    if hasattr(user, "updated_at"):
        user.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user)

    role = db.query(Role).filter(Role.role_id == user.role_id).first()

    return {
        "message": "Đã mở khóa tài khoản" if payload.is_active else "Đã khóa tài khoản",
        "user": admin_serialize_user(user, role)
    }

# ============================================================
# ADMIN TASK PIPELINE
# ============================================================

ADMIN_TASKS: dict[str, dict[str, Any]] = {}
MAX_ADMIN_TASK_HISTORY = 80


def payload_to_dict(payload: BaseModel):
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return payload.dict()


def admin_task_now():
    return datetime.now(timezone.utc).isoformat()


def trim_admin_task_history():
    if len(ADMIN_TASKS) <= MAX_ADMIN_TASK_HISTORY:
        return

    sorted_ids = sorted(
        ADMIN_TASKS.keys(),
        key=lambda task_id: ADMIN_TASKS[task_id].get("created_at") or "",
        reverse=True
    )

    keep_ids = set(sorted_ids[:MAX_ADMIN_TASK_HISTORY])

    for task_id in list(ADMIN_TASKS.keys()):
        if task_id not in keep_ids:
            ADMIN_TASKS.pop(task_id, None)


def serialize_admin_task(task: AdminTask):
    return {
        "task_id": str(task.task_id),
        "task_type": task.task_type,
        "title": task.title,
        "status": task.status,
        "parameters": task.parameters or {},
        "logs": task.logs or [],
        "result": task.result,
        "error": task.error_message,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }


def create_admin_task(task_type: str, title: str, parameters: dict[str, Any]):
    """
    Tạo task trong DB để lịch sử không bị mất khi F5/restart backend.
    Vẫn ghi thêm vào ADMIN_TASKS để giữ tương thích với code frontend cũ.
    """
    db = SessionLocal()

    try:
        db_task = AdminTask(
            task_type=task_type,
            title=title,
            status="queued",
            parameters=parameters,
            logs=[],
            result=None,
            error_message=None,
            created_at=datetime.now(timezone.utc)
        )

        db.add(db_task)
        db.commit()
        db.refresh(db_task)

        task = serialize_admin_task(db_task)
        ADMIN_TASKS[task["task_id"]] = task
        trim_admin_task_history()

        return task

    except Exception:
        db.rollback()

        # Fallback: nếu DB chưa tạo bảng admin_tasks, hệ thống vẫn chạy bằng RAM như cũ.
        task_id = str(uuid4())

        ADMIN_TASKS[task_id] = {
            "task_id": task_id,
            "task_type": task_type,
            "title": title,
            "status": "queued",
            "parameters": parameters,
            "logs": [],
            "result": None,
            "error": None,
            "created_at": admin_task_now(),
            "started_at": None,
            "completed_at": None,
        }

        trim_admin_task_history()
        return ADMIN_TASKS[task_id]

    finally:
        db.close()


def append_admin_task_log(task_id: str, message: str):
    # 1. Cập nhật RAM để frontend cũ vẫn đọc được ngay.
    task = ADMIN_TASKS.get(str(task_id))

    log_item = {
        "time": admin_task_now(),
        "message": message,
    }

    if task:
        task["logs"].append(log_item)
        task["logs"] = task["logs"][-80:]

    # 2. Cập nhật DB để lịch sử task không bị mất.
    db = SessionLocal()

    try:
        if str(task_id).isdigit():
            db_task = db.query(AdminTask).filter(AdminTask.task_id == int(task_id)).first()

            if db_task:
                logs = list(db_task.logs or [])
                logs.append(log_item)
                db_task.logs = logs[-120:]
                db.commit()

    except Exception:
        db.rollback()

    finally:
        db.close()


def update_admin_task(task_id: str, **kwargs):
    task = ADMIN_TASKS.get(str(task_id))

    if task:
        task.update(kwargs)

        if "error_message" in kwargs and "error" not in kwargs:
            task["error"] = kwargs["error_message"]

        if kwargs.get("status") == "running" and not task.get("started_at"):
            task["started_at"] = admin_task_now()

        if kwargs.get("status") in ["completed", "failed", "cancelled"]:
            task["completed_at"] = admin_task_now()

    db = SessionLocal()

    try:
        if str(task_id).isdigit():
            db_task = db.query(AdminTask).filter(AdminTask.task_id == int(task_id)).first()

            if db_task:
                status = kwargs.get("status")

                if status:
                    db_task.status = status

                    if status == "running" and not db_task.started_at:
                        db_task.started_at = datetime.now(timezone.utc)

                    if status in ["completed", "failed", "cancelled"]:
                        db_task.completed_at = datetime.now(timezone.utc)

                if "started_at" in kwargs and kwargs["started_at"]:
                    db_task.started_at = datetime.now(timezone.utc)

                if "completed_at" in kwargs and kwargs["completed_at"]:
                    db_task.completed_at = datetime.now(timezone.utc)

                if "result" in kwargs:
                    db_task.result = kwargs["result"]

                if "error" in kwargs:
                    db_task.error_message = kwargs["error"]

                if "error_message" in kwargs:
                    db_task.error_message = kwargs["error_message"]

                db.commit()

    except Exception:
        db.rollback()

    finally:
        db.close()


def run_admin_background_task(task_id, job_func, parameters):
    try:
        update_admin_task(
            task_id,
            status="running",
            started_at=True
        )

        append_admin_task_log(task_id, "Task started.")

        def should_stop():
            return is_task_cancel_requested(task_id)

        result = job_func(
            task_id,
            parameters,
            should_stop=should_stop
        )

        if is_task_cancel_requested(task_id):
            update_admin_task(
                task_id,
                status="cancelled",
                completed_at=True,
                result={
                    "message": "Task đã được dừng bởi admin."
                }
            )
            append_admin_task_log(task_id, "Task cancelled by admin.")
            return

        if isinstance(result, dict) and result.get("status") == "cancelled":
            update_admin_task(
                task_id,
                status="cancelled",
                completed_at=True,
                result=result
            )
            append_admin_task_log(task_id, "Task cancelled by admin.")
            return

        update_admin_task(
            task_id,
            status="completed",
            completed_at=True,
            result=result or {}
        )

        append_admin_task_log(task_id, "Task completed.")

    except Exception as error:
        if is_task_cancel_requested(task_id):
            update_admin_task(
                task_id,
                status="cancelled",
                completed_at=True,
                error="Task đã được dừng bởi admin."
            )
            append_admin_task_log(task_id, "Task cancelled by admin.")
            return

        update_admin_task(
            task_id,
            status="failed",
            completed_at=True,
            error=str(error)
        )

        append_admin_task_log(task_id, f"Task failed: {str(error)}")


def run_crawl_hashtags_job(task_id: str, parameters: dict[str, Any], should_stop=None):
    hashtags = parameters["hashtags"]
    max_videos = int(parameters.get("max_videos") or 300)
    max_scrolls = int(parameters.get("max_scrolls") or 30)
    cookies_file = parameters.get("cookies_file") or "cookies.json"

    def stop_requested():
        return should_stop is not None and should_stop()

    clean_hashtags = [
        hashtag.strip().replace("#", "")
        for hashtag in hashtags
        if hashtag and hashtag.strip()
    ]

    if not clean_hashtags:
        raise RuntimeError("Không có hashtag hợp lệ để crawl.")

    hashtags_arg = ",".join(clean_hashtags)

    append_admin_task_log(
        task_id,
        (
            "Launching crawler subprocess | "
            f"hashtags={hashtags_arg}, "
            f"max_videos={max_videos}, "
            f"max_scrolls={max_scrolls}, "
            f"cookies_file={cookies_file}"
        )
    )

    command = [
        sys.executable,
        "-u",
        "-m",
        "crawler.hashtag_crawler_with_cookies",
        "--hashtags",
        hashtags_arg,
        "--max-videos",
        str(max_videos),
        "--max-scrolls",
        str(max_scrolls),
        "--cookies-file",
        cookies_file,
    ]

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        cwd=Path.cwd(),
        env=env,
    )

    log_tail = []

    try:
        while True:
            if stop_requested():
                append_admin_task_log(
                    task_id,
                    "Admin requested crawler stop. Terminating crawler subprocess..."
                )

                process.terminate()

                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)

                return {
                    "status": "cancelled",
                    "hashtags": clean_hashtags,
                    "max_videos": max_videos,
                    "max_scrolls": max_scrolls,
                    "message": "Crawler đã được dừng bởi admin.",
                }

            line = process.stdout.readline() if process.stdout else ""

            if line:
                clean_line = line.strip()

                if clean_line:
                    log_tail.append(clean_line)
                    log_tail = log_tail[-80:]

                    # Chỉ đẩy các log quan trọng lên Admin để tránh quá dài.
                    important_keywords = [
                        "🚀",
                        "🎯",
                        "✅",
                        "❌",
                        "⚠️",
                        "📊",
                        "📦",
                        "📁",
                        "💾",
                        "CAPTCHA",
                        "Slider",
                        "Success",
                        "Extracted",
                        "saved",
                        "failed",
                        "blocked",
                        "Validation",
                    ]

                    if any(keyword in clean_line for keyword in important_keywords):
                        append_admin_task_log(task_id, clean_line)

            if process.poll() is not None:
                # Đọc nốt phần log còn lại.
                if process.stdout:
                    remaining = process.stdout.read()

                    if remaining:
                        for item in remaining.splitlines():
                            item = item.strip()

                            if item:
                                log_tail.append(item)

                break

            time.sleep(0.1)

        return_code = process.returncode

        if return_code != 0:
            error_tail = "\n".join(log_tail[-30:])

            append_admin_task_log(
                task_id,
                f"Crawler subprocess failed with code={return_code}"
            )

            if error_tail:
                append_admin_task_log(task_id, error_tail[-2500:])

            raise RuntimeError(
                error_tail or f"Crawler subprocess failed with code={return_code}"
            )

        append_admin_task_log(
            task_id,
            "Crawler subprocess completed successfully."
        )

        return {
            "status": "completed",
            "hashtags": clean_hashtags,
            "max_videos": max_videos,
            "max_scrolls": max_scrolls,
            "cookies_file": cookies_file,
            "stdout_tail": "\n".join(log_tail[-30:]),
            "message": "Crawler subprocess completed.",
        }

    except Exception:
        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=10)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

        raise

def run_yolo_process_job(task_id: str, parameters: dict[str, Any], should_stop=None):
    batch_size = int(parameters.get("batch_size") or 20)
    confidence = float(parameters.get("confidence") or 0.4)
    model_path = parameters.get("model_path") or "ai/models/yolov8m_fashion_best.pt"

    append_admin_task_log(
        task_id,
        f"Starting YOLOv8 processing | batch_size={batch_size}, confidence={confidence}"
    )

    try:
        from ai.batch_vision_processor_final import FashionBatchProcessor
    except ModuleNotFoundError:
        from ai.batch_vision_processor_final import FashionBatchProcessor

    processor = FashionBatchProcessor(model_path=model_path)

    try:
        result = processor.process_all_videos(
            batch_size=batch_size,
            conf=confidence,
            should_stop=should_stop
        )

        if isinstance(result, dict):
            processed_count = result.get("processed_count", 0)
        else:
            processed_count = result

        append_admin_task_log(
            task_id,
            f"YOLOv8 processed {processed_count} videos."
        )

        if isinstance(result, dict):
            result.update({
                "model_path": model_path,
                "batch_size": batch_size,
                "confidence": confidence,
            })
            return result

        return {
            "status": "completed",
            "processed_count": processed_count,
            "model_path": model_path,
            "batch_size": batch_size,
            "confidence": confidence,
        }

    finally:
        try:
            processor.db.close()
        except Exception:
            pass


def run_sync_stats_job(task_id: str, parameters: dict[str, Any], should_stop=None):
    hours_gap = int(parameters.get("hours_gap", 16))
    limit = int(parameters.get("limit", 2500))

    append_admin_task_log(
        task_id,
        f"Starting sync video stats | hours_gap={hours_gap}, limit={limit}"
    )

    # Fix Playwright asyncio subprocess trên Windows
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass

    syncer = VideoStatsSyncer()

    try:
        result = asyncio.run(
            syncer.sync_all_stats(
                hours_gap=hours_gap,
                limit=limit,
                should_stop=should_stop
            )
        )

        append_admin_task_log(
            task_id,
            f"Sync video stats finished | result={result}"
        )

        return result

    finally:
        try:
            syncer.db.close()
        except Exception:
            pass

def run_build_trend_history_job(task_id: str, parameters: dict[str, Any], should_stop=None):
    start_date = parameters.get("start_date")
    end_date = parameters.get("end_date")
    min_distinct_stat_days = int(parameters.get("min_distinct_stat_days") or 4)
    clean_before_build = bool(parameters.get("clean_before_build"))

    if not start_date or not end_date:
        raise RuntimeError("Thiếu start_date hoặc end_date.")

    append_admin_task_log(
        task_id,
        (
            f"Building trend_history | "
            f"start_date={start_date}, end_date={end_date}, "
            f"min_distinct_stat_days={min_distinct_stat_days}, "
            f"clean_before_build={clean_before_build}"
        )
    )

    from ai.trend_history_builder import TrendHistoryBuilder

    db_session = SessionLocal()

    try:
        builder = TrendHistoryBuilder(db_session)

        build_result = builder.build_daily_history(
            start_date_str=start_date,
            end_date_str=end_date,
            min_distinct_stat_days=min_distinct_stat_days,
            clean_before_build=clean_before_build,
            should_stop=should_stop,
        )

        append_admin_task_log(
            task_id,
            "Build trend_history completed."
        )

        if isinstance(build_result, dict) and build_result.get("status") == "cancelled":
            return build_result

        return {
            "status": "completed",
            "start_date": start_date,
            "end_date": end_date,
            "min_distinct_stat_days": min_distinct_stat_days,
            "clean_before_build": clean_before_build,
            "message": "Build trend_history completed.",
        }

    except Exception as e:
        db_session.rollback()
        append_admin_task_log(
            task_id,
            f"Build trend_history failed: {str(e)}"
        )
        raise e

    finally:
        db_session.close()

def run_lstm_prediction_job(task_id: str, parameters: dict[str, Any], should_stop=None):
    raw_limit = parameters.get("limit")
    limit = int(raw_limit) if raw_limit not in [None, "", 0, "0"] else None

    append_admin_task_log(
        task_id,
        f"Running LSTM prediction | limit={limit or 'all'}"
    )

    from ai.trend_history_predictor import TrendHistoryPredictor

    predictor = TrendHistoryPredictor()
    prediction_result = predictor.run_batch_prediction(limit=limit, should_stop=should_stop)

    if isinstance(prediction_result, dict):
        prediction_result["limit"] = limit
        return prediction_result

    return {
        "status": "completed",
        "saved_count": prediction_result,
        "limit": limit,
        "message": "LSTM prediction completed."
    }


def run_evaluate_predictions_job(task_id: str, parameters: dict[str, Any], should_stop=None):
    raw_limit = parameters.get("limit")
    limit = int(raw_limit) if raw_limit not in [None, "", 0, "0"] else None

    append_admin_task_log(
        task_id,
        f"Evaluating predictions | limit={limit or 'all'}"
    )

    from ai.prediction_evaluator import PredictionEvaluator

    evaluator = PredictionEvaluator()

    result = evaluator.evaluate_predictions(
        limit=limit,
        should_stop=should_stop
    )

    append_admin_task_log(
        task_id,
        f"Evaluate predictions finished | result={result}"
    )

    return result


def run_backup_database_job(task_id: str, parameters: dict[str, Any], should_stop=None):
    file_prefix = parameters.get("file_prefix") or "backup"
    timeout_seconds = int(parameters.get("timeout_seconds") or 300)

    def stop_requested():
        return should_stop is not None and should_stop()

    if stop_requested():
        return {
            "status": "cancelled",
            "message": "Backup đã được dừng bởi admin."
        }

    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_prefix = "".join(
        char for char in file_prefix
        if char.isalnum() or char in ["_", "-"]
    ) or "backup"

    backup_file = backup_dir / f"{safe_prefix}_{timestamp}.sql"

    pg_dump_path = shutil.which("pg_dump")

    pg_dump_path = (
        os.getenv("PG_DUMP_PATH")
        or shutil.which("pg_dump")
    )

    if not pg_dump_path:
        possible_paths = [
            r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe",
            r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe",
            r"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe",
            r"C:\Program Files\PostgreSQL\14\bin\pg_dump.exe",
            r"C:\Program Files\PostgreSQL\13\bin\pg_dump.exe",
        ]

        for path in possible_paths:
            if os.path.exists(path):
                pg_dump_path = path
                break

    if not pg_dump_path:
        raise RuntimeError(
            "Không tìm thấy pg_dump.exe. Hãy kiểm tra PostgreSQL đã cài chưa, "
            "hoặc thêm đường dẫn PostgreSQL/bin vào PATH, ví dụ: "
            "C:\\Program Files\\PostgreSQL\\16\\bin"
        )

    database_url = os.getenv("DATABASE_URL")

    env = os.environ.copy()

    if database_url:
        command = [
            pg_dump_path,
            database_url,
            "-f",
            str(backup_file)
        ]
    else:
        db_name = (
            os.getenv("POSTGRES_DB")
            or os.getenv("DB_NAME")
            or os.getenv("DATABASE_NAME")
            or "TikTokFashionTrend"
        )

        db_user = (
            os.getenv("POSTGRES_USER")
            or os.getenv("DB_USER")
            or "postgres"
        )

        db_host = os.getenv("POSTGRES_HOST") or os.getenv("DB_HOST")
        db_port = os.getenv("POSTGRES_PORT") or os.getenv("DB_PORT")
        db_password = os.getenv("POSTGRES_PASSWORD") or os.getenv("DB_PASSWORD")

        if db_password:
            env["PGPASSWORD"] = db_password

        command = [
            pg_dump_path,
            "-U",
            db_user,
            "-d",
            db_name,
            "-f",
            str(backup_file)
        ]

        if db_host:
            command.extend(["-h", db_host])

        if db_port:
            command.extend(["-p", db_port])

    append_admin_task_log(
        task_id,
        f"Creating database backup: {backup_file}"
    )

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )

    started = time.time()

    while process.poll() is None:
        if stop_requested():
            append_admin_task_log(task_id, "Admin requested backup stop. Terminating pg_dump...")
            process.terminate()

            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate(timeout=10)

            return {
                "status": "cancelled",
                "message": "Backup đã được dừng bởi admin."
            }

        if time.time() - started > timeout_seconds:
            process.kill()
            stdout, stderr = process.communicate(timeout=10)
            raise RuntimeError(stderr[-1500:] or "pg_dump timeout.")

        time.sleep(1)

    stdout, stderr = process.communicate(timeout=10)

    if process.returncode != 0:
        raise RuntimeError(stderr[-1500:] or "pg_dump failed.")

    return {
        "status": "completed",
        "backup_file": str(backup_file),
        "file_size_bytes": backup_file.stat().st_size if backup_file.exists() else 0,
        "message": "Database backup completed."
    }


@router.get("/tasks/history")
def get_admin_task_history(
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin)
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
        reverse=True
    )

    return {
        "items": items[:MAX_ADMIN_TASK_HISTORY]
    }



@router.get("/tasks/{task_id}")
def get_admin_task_detail(
    task_id: str,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin)
):
    if task_id.isdigit():
        db_task = db.query(AdminTask).filter(AdminTask.task_id == int(task_id)).first()

        if db_task:
            return serialize_admin_task(db_task)

    task = ADMIN_TASKS.get(task_id)

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy task."
        )

    return task



@router.post("/tasks/crawl-hashtags")
def task_crawl_hashtags(
    payload: CrawlHashtagsTaskRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(require_admin)
):
    hashtags = [
        item.strip().replace("#", "")
        for item in payload.hashtags
        if item and item.strip()
    ]

    if not hashtags:
        raise HTTPException(
            status_code=400,
            detail="Vui lòng nhập ít nhất một hashtag."
        )

    if payload.max_videos <= 0 or payload.max_videos > 3000:
        raise HTTPException(
            status_code=400,
            detail="max_videos phải nằm trong khoảng 1 đến 3000."
        )

    if payload.max_scrolls <= 0 or payload.max_scrolls > 300:
        raise HTTPException(
            status_code=400,
            detail="max_scrolls phải nằm trong khoảng 1 đến 300."
        )

    parameters = payload_to_dict(payload)
    parameters["hashtags"] = hashtags
    parameters = apply_demo_limits("crawl_hashtags", parameters)

    task = create_admin_task(
        task_type="crawl_hashtags",
        title="Crawl TikTok Hashtags",
        parameters=parameters
    )

    background_tasks.add_task(
        run_admin_background_task,
        task["task_id"],
        run_crawl_hashtags_job,
        parameters
    )

    return {
        "message": "Đã bắt đầu crawl hashtags.",
        "task": task
    }


@router.post("/tasks/process-yolo")
def task_process_yolo(
    payload: YoloProcessTaskRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(require_admin)
):
    if payload.batch_size <= 0 or payload.batch_size > 200:
        raise HTTPException(
            status_code=400,
            detail="batch_size phải nằm trong khoảng 1 đến 200."
        )

    if payload.confidence <= 0 or payload.confidence >= 1:
        raise HTTPException(
            status_code=400,
            detail="confidence phải nằm trong khoảng 0 đến 1."
        )

    parameters = payload_to_dict(payload)
    parameters = apply_demo_limits("process_yolo", parameters)

    task = create_admin_task(
        task_type="process_yolo",
        title="YOLOv8 Fashion Detection",
        parameters=parameters
    )

    background_tasks.add_task(
        run_admin_background_task,
        task["task_id"],
        run_yolo_process_job,
        parameters
    )

    return {
        "message": "Đã bắt đầu xử lý YOLOv8.",
        "task": task
    }


@router.post("/tasks/sync-stats")
def task_sync_stats(
    payload: SyncStatsTaskRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(require_admin)
):
    if payload.hours_gap <= 0 or payload.hours_gap > 720:
        raise HTTPException(
            status_code=400,
            detail="hours_gap phải nằm trong khoảng 1 đến 720."
        )

    if payload.limit <= 0 or payload.limit > 20000:
        raise HTTPException(
            status_code=400,
            detail="limit phải nằm trong khoảng 1 đến 20000."
        )

    parameters = payload_to_dict(payload)
    parameters = apply_demo_limits("sync_stats", parameters)

    task = create_admin_task(
        task_type="sync_stats",
        title="Sync Video Stats",
        parameters=parameters
    )

    background_tasks.add_task(
        run_admin_background_task,
        task["task_id"],
        run_sync_stats_job,
        parameters
    )

    return {
        "message": "Đã bắt đầu sync video_stats.",
        "task": task
    }


@router.post("/tasks/build-trend-history")
def task_build_trend_history(
    payload: BuildTrendHistoryTaskRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(require_admin)
):
    if not payload.start_date or not payload.end_date:
        raise HTTPException(
            status_code=400,
            detail="Vui lòng nhập start_date và end_date."
        )

    if payload.min_distinct_stat_days <= 0 or payload.min_distinct_stat_days > 30:
        raise HTTPException(
            status_code=400,
            detail="min_distinct_stat_days phải nằm trong khoảng 1 đến 30."
        )

    parameters = payload_to_dict(payload)

    task = create_admin_task(
        task_type="build_trend_history",
        title="Build Trend History",
        parameters=parameters
    )

    background_tasks.add_task(
        run_admin_background_task,
        task["task_id"],
        run_build_trend_history_job,
        parameters
    )

    return {
        "message": "Đã bắt đầu build trend_history.",
        "task": task
    }


@router.post("/tasks/run-prediction")
def task_run_prediction(
    payload: PredictionTaskRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(require_admin)
):
    parameters = payload_to_dict(payload)
    parameters = apply_demo_limits("run_prediction", parameters)

    if parameters.get("limit") is not None and int(parameters["limit"]) <= 0:
        raise HTTPException(
            status_code=400,
            detail="limit phải lớn hơn 0 hoặc để trống."
        )

    task = create_admin_task(
        task_type="run_prediction",
        title="Run LSTM Prediction",
        parameters=parameters
    )

    background_tasks.add_task(
        run_admin_background_task,
        task["task_id"],
        run_lstm_prediction_job,
        parameters
    )

    return {
        "message": "Đã bắt đầu chạy LSTM prediction.",
        "task": task
    }


@router.post("/tasks/evaluate-predictions")
def task_evaluate_predictions(
    payload: EvaluatePredictionsTaskRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(require_admin)
):
    parameters = payload_to_dict(payload)
    parameters = apply_demo_limits("evaluate_predictions", parameters)

    if parameters.get("limit") is not None and int(parameters["limit"]) <= 0:
        raise HTTPException(
            status_code=400,
            detail="limit phải lớn hơn 0 hoặc để trống."
        )

    task = create_admin_task(
        task_type="evaluate_predictions",
        title="Evaluate LSTM Predictions",
        parameters=parameters
    )

    background_tasks.add_task(
        run_admin_background_task,
        task["task_id"],
        run_evaluate_predictions_job,
        parameters
    )

    return {
        "message": "Đã bắt đầu đánh giá kết quả dự đoán.",
        "task": task
    }


@router.post("/tasks/backup-database")
def task_backup_database(
    payload: BackupDatabaseTaskRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(require_admin)
):
    parameters = payload_to_dict(payload)

    task = create_admin_task(
        task_type="backup_database",
        title="Backup Database",
        parameters=parameters
    )

    background_tasks.add_task(
        run_admin_background_task,
        task["task_id"],
        run_backup_database_job,
        parameters
    )

    return {
        "message": "Đã bắt đầu backup database.",
        "task": task
    }


# ============================================================
# ADMIN OVERVIEW / QUALITY / MODEL EVALUATION
# ============================================================


@router.get("/system/data-quality-summary")
def get_data_quality_summary(
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin)
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
        Video.is_analyzed == True
    ).scalar() or 0

    pending_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "pending"
    ).scalar() or 0

    yolo_success = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "success",
        Video.is_analyzed == True,
    ).scalar() or 0

    failed_no_fashion = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "failed_no_fashion"
    ).scalar() or 0

    uncertain_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "uncertain"
    ).scalar() or 0

    failed_no_frame = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status.in_(["failed_no_frame", "failed_no_frame_final"])
    ).scalar() or 0

    error_videos = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "error"
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
        Prediction.prediction_type == "view_growth"
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
    current_admin=Depends(require_admin)
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
        Video.processing_status == "failed_no_fashion"
    ).scalar() or 0

    uncertain = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "uncertain"
    ).scalar() or 0

    failed_no_frame = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status.in_(["failed_no_frame", "failed_no_frame_final"])
    ).scalar() or 0

    error = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "error"
    ).scalar() or 0

    pending = db.query(func.count(Video.video_id)).filter(
        Video.is_in_scope == True,
        Video.processing_status == "pending"
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
        FashionItem.confidence.isnot(None)
    ).scalar()

    latest_ai_ids = (
        db.query(
            AIAnalysis.video_id.label("video_id"),
            func.max(AIAnalysis.analysis_id).label("latest_analysis_id")
        )
        .join(Video, Video.video_id == AIAnalysis.video_id)
        .filter(Video.is_in_scope == True)
        .filter(AIAnalysis.analysis_type == "vision")
        .filter(AIAnalysis.result_json["result_kind"].astext == "fashion_relevance")
        .group_by(AIAnalysis.video_id)
        .subquery()
    )

    avg_relevance_confidence = db.query(
        func.avg(AIAnalysis.confidence_score)
    ).join(
        latest_ai_ids,
        AIAnalysis.analysis_id == latest_ai_ids.c.latest_analysis_id
    ).filter(
        AIAnalysis.confidence_score.isnot(None)
    ).scalar()

    total_analysis = db.query(func.count(AIAnalysis.analysis_id)).join(
        Video, Video.video_id == AIAnalysis.video_id
    ).filter(
        Video.is_in_scope == True,
        AIAnalysis.analysis_type == "vision",
        AIAnalysis.result_json["result_kind"].astext == "fashion_relevance"
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
        Prediction.accuracy_score.isnot(None)
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
    current_admin=Depends(require_admin)
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
    current_user: User = Depends(require_admin)
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
        }
    }

@router.get("/users/advanced")
def get_users_advanced(
    search: str | None = None,
    role: str | None = None,
    verified: str | None = None,
    active: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    query = db.query(User, Role).outerjoin(Role, User.role_id == Role.role_id)

    if search:
        keyword = f"%{search.lower()}%"
        query = query.filter(
            or_(
                func.lower(User.username).like(keyword),
                func.lower(User.email).like(keyword),
                func.lower(User.full_name).like(keyword)
            )
        )

    if role and role != "all":
        query = query.filter(func.lower(Role.role_name) == role.lower())

    if verified == "verified":
        query = query.filter(User.is_email_verified == True)

    if verified == "unverified":
        query = query.filter(User.is_email_verified == False)

    if active == "active":
        query = query.filter(User.is_active == True)

    if active == "locked":
        query = query.filter(User.is_active == False)

    rows = query.order_by(desc(User.created_at)).limit(limit).all()

    return [
        admin_serialize_user(user, user_role)
        for user, user_role in rows
    ]

@router.get("/system-health")
def get_system_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
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


@router.post("/tasks/{task_id}/cancel")
def cancel_admin_task(
    task_id: int,
    current_admin=Depends(require_admin)
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
                "status": task.status
            }

        task.status = "cancel_requested"

        logs = task.logs or []
        logs.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "message": "Admin đã yêu cầu dừng tác vụ."
        })

        task.logs = logs
        db.commit()

        return {
            "message": "Đã gửi yêu cầu dừng task.",
            "task_id": task_id,
            "status": "cancel_requested"
        }

    finally:
        db.close()

def is_task_cancel_requested(task_id: int) -> bool:
    db = SessionLocal()

    try:
        task = db.query(AdminTask).filter(AdminTask.task_id == task_id).first()

        if not task:
            return False

        return task.status == "cancel_requested"

    finally:
        db.close()