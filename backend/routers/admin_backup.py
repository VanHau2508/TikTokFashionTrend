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
from uuid import uuid4
from typing import Any

from database.config import SessionLocal
from database.models import (
    User,
    Role,
    Video,
    VideoStat,
    Hashtag,
    FashionItem,
    Prediction,
    CrawlerJob
)

router = APIRouter(prefix="/api/admin", tags=["Admin"])

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


def create_admin_task(task_type: str, title: str, parameters: dict[str, Any]):
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


def append_admin_task_log(task_id: str, message: str):
    task = ADMIN_TASKS.get(task_id)

    if not task:
        return

    task["logs"].append({
        "time": admin_task_now(),
        "message": message,
    })

    # Giữ log gọn, tránh response quá nặng
    task["logs"] = task["logs"][-80:]


def update_admin_task(task_id: str, **kwargs):
    task = ADMIN_TASKS.get(task_id)

    if not task:
        return

    task.update(kwargs)


def run_admin_background_task(task_id: str, runner, parameters: dict[str, Any]):
    update_admin_task(
        task_id,
        status="running",
        started_at=admin_task_now()
    )

    append_admin_task_log(task_id, "Task started.")

    try:
        result = runner(task_id, parameters)

        update_admin_task(
            task_id,
            status="completed",
            completed_at=admin_task_now(),
            result=result,
        )

        append_admin_task_log(task_id, "Task completed successfully.")

    except Exception as e:
        update_admin_task(
            task_id,
            status="failed",
            completed_at=admin_task_now(),
            error=str(e),
        )

        append_admin_task_log(task_id, f"Task failed: {str(e)}")


def run_crawl_hashtags_job(task_id: str, parameters: dict[str, Any]):
    hashtags = parameters["hashtags"]
    max_videos = int(parameters.get("max_videos") or 300)
    max_scrolls = int(parameters.get("max_scrolls") or 30)
    cookies_file = parameters.get("cookies_file") or "cookies.json"

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
        f"Launching crawler subprocess | hashtags={hashtags_arg}, max_videos={max_videos}, max_scrolls={max_scrolls}"
    )

    command = [
        sys.executable,
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

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=60 * 60,
        cwd=Path.cwd(),
    )

    stdout_tail = result.stdout[-3000:] if result.stdout else ""
    stderr_tail = result.stderr[-3000:] if result.stderr else ""

    if stdout_tail:
        append_admin_task_log(task_id, stdout_tail)

    if result.returncode != 0:
        if stderr_tail:
            append_admin_task_log(task_id, stderr_tail)

        raise RuntimeError(
            stderr_tail or "Crawler subprocess failed."
        )

    return {
        "hashtags": clean_hashtags,
        "max_videos": max_videos,
        "max_scrolls": max_scrolls,
        "stdout_tail": stdout_tail,
        "message": "Crawler subprocess completed."
    }

def run_yolo_process_job(task_id: str, parameters: dict[str, Any]):
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
        processed_count = processor.process_all_videos(
            batch_size=batch_size,
            conf=confidence
        )

        append_admin_task_log(
            task_id,
            f"YOLOv8 processed {processed_count} videos."
        )

        return {
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


def run_sync_stats_job(task_id: str, parameters: dict[str, Any]):
    hours_gap = int(parameters.get("hours_gap") or 16)
    limit = int(parameters.get("limit") or 2500)

    append_admin_task_log(
        task_id,
        f"Launching sync stats subprocess | hours_gap={hours_gap}, limit={limit}"
    )

    command = [
        sys.executable,
        "-m",
        "crawler.sync_video_stats",
        "--hours-gap",
        str(hours_gap),
        "--limit",
        str(limit),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=60 * 60,
        cwd=Path.cwd(),
    )

    stdout_tail = result.stdout[-3000:] if result.stdout else ""
    stderr_tail = result.stderr[-3000:] if result.stderr else ""

    if stdout_tail:
        append_admin_task_log(task_id, stdout_tail)

    if result.returncode != 0:
        if stderr_tail:
            append_admin_task_log(task_id, stderr_tail)

        raise RuntimeError(
            stderr_tail or "Sync video stats subprocess failed."
        )

    return {
        "hours_gap": hours_gap,
        "limit": limit,
        "stdout_tail": stdout_tail,
        "message": "Sync video_stats subprocess completed."
    }
def run_build_trend_history_job(task_id: str, parameters: dict[str, Any]):
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

        builder.build_daily_history(
            start_date_str=start_date,
            end_date_str=end_date,
            min_distinct_stat_days=min_distinct_stat_days,
            clean_before_build=clean_before_build,
        )

        append_admin_task_log(
            task_id,
            "Build trend_history completed."
        )

        return {
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

def run_lstm_prediction_job(task_id: str, parameters: dict[str, Any]):
    raw_limit = parameters.get("limit")
    limit = int(raw_limit) if raw_limit not in [None, "", 0, "0"] else None

    append_admin_task_log(
        task_id,
        f"Running LSTM prediction | limit={limit or 'all'}"
    )

    from ai.trend_history_predictor import TrendHistoryPredictor

    predictor = TrendHistoryPredictor()
    saved_count = predictor.run_batch_prediction(limit=limit)

    return {
        "saved_count": saved_count,
        "limit": limit,
        "message": "LSTM prediction completed."
    }


def run_backup_database_job(task_id: str, parameters: dict[str, Any]):
    file_prefix = parameters.get("file_prefix") or "backup"
    timeout_seconds = int(parameters.get("timeout_seconds") or 300)

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

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env=env
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1500:] or "pg_dump failed.")

    return {
        "backup_file": str(backup_file),
        "file_size_bytes": backup_file.stat().st_size if backup_file.exists() else 0,
        "message": "Database backup completed."
    }


@router.get("/tasks/history")
def get_admin_task_history(current_admin=Depends(require_admin)):
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
    current_admin=Depends(require_admin)
):
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

    total_videos = db.query(func.count(Video.video_id)).scalar() or 0

    yolo_success = db.query(func.count(Video.video_id)).filter(
        Video.processing_status == "success"
    ).scalar() or 0

    total_hashtags = db.query(func.count(Hashtag.hashtag_id)).scalar() or 0

    total_items = db.query(func.count(FashionItem.item_id)).scalar() or 0

    total_predictions = db.query(func.count(Prediction.prediction_id)).scalar() or 0

    jobs_total = db.query(func.count(CrawlerJob.job_id)).scalar() or 0

    jobs_completed = db.query(func.count(CrawlerJob.job_id)).filter(
        CrawlerJob.status == "completed"
    ).scalar() or 0

    jobs_failed = db.query(func.count(CrawlerJob.job_id)).filter(
        CrawlerJob.status == "failed"
    ).scalar() or 0

    latest_stat = db.query(VideoStat).order_by(
        desc(VideoStat.collected_at)
    ).first()

    latest_prediction = db.query(Prediction).order_by(
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
            "yolo": "ready" if os.path.exists("ai/models/yolov8m_fashion_best.pt") else "missing_model",
            "lstm": "ready" if os.path.exists("ai/models/lstm_trend_history_growth_model.h5") else "missing_model",
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
            "path": "ai/models/yolov8m_fashion_best.pt",
            "exists": os.path.exists("ai/models/yolov8m_fashion_best.pt"),
        },
        "lstm_model": {
            "path": "ai/models/lstm_trend_history_growth_model.h5",
            "exists": os.path.exists("ai/models/lstm_trend_history_growth_model.h5"),
        },
        "feature_scaler": {
            "path": "ai/models/trend_history_feature_scaler.pkl",
            "exists": os.path.exists("ai/models/trend_history_feature_scaler.pkl"),
        },
        "target_scaler": {
            "path": "ai/models/trend_history_target_scaler.pkl",
            "exists": os.path.exists("ai/models/trend_history_target_scaler.pkl"),
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