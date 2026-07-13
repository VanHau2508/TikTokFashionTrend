import os
import sys
import asyncio
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from crawler.sync_video_stats import VideoStatsSyncer
from database.config import SessionLocal
from database.models import AdminTask

# ============================================================
# Constants / config
# ============================================================

LSTM_V3_MODEL_VERSION = "lstm_trend_history_growth_v3"

YOLO_MODEL_PATH = "ai/models/yolov8m_fashion_best.pt"

LSTM_V3_MODEL_DIR = "ai/models/lstm_trend_history_v3"
LSTM_V3_MODEL_PATH = f"{LSTM_V3_MODEL_DIR}/lstm_trend_history_growth_model_v3.keras"
LSTM_V3_FEATURE_SCALER_PATH = f"{LSTM_V3_MODEL_DIR}/trend_history_feature_scaler_v3.pkl"
LSTM_V3_TARGET_SCALER_PATH = f"{LSTM_V3_MODEL_DIR}/trend_history_target_scaler_v3.pkl"
LSTM_V3_CONFIG_PATH = f"{LSTM_V3_MODEL_DIR}/lstm_trend_history_growth_config_v3.json"

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

ADMIN_TASKS: dict[str, dict[str, Any]] = {}
MAX_ADMIN_TASK_HISTORY = 80


def is_lstm_v3_ready():
    return (
        os.path.exists(LSTM_V3_MODEL_PATH)
        and os.path.exists(LSTM_V3_FEATURE_SCALER_PATH)
        and os.path.exists(LSTM_V3_TARGET_SCALER_PATH)
        and os.path.exists(LSTM_V3_CONFIG_PATH)
    )


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


# ============================================================
# Request models for admin tasks
# ============================================================

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


# ============================================================
# Task storage / logging
# ============================================================

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
        reverse=True,
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
            created_at=datetime.now(timezone.utc),
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
    task = ADMIN_TASKS.get(str(task_id))

    log_item = {
        "time": admin_task_now(),
        "message": message,
    }

    if task:
        task["logs"].append(log_item)
        task["logs"] = task["logs"][-80:]

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


def is_task_cancel_requested(task_id: int | str) -> bool:
    db = SessionLocal()

    try:
        if not str(task_id).isdigit():
            return False

        task = db.query(AdminTask).filter(AdminTask.task_id == int(task_id)).first()

        if not task:
            return False

        return task.status == "cancel_requested"

    finally:
        db.close()


def run_admin_background_task(task_id, job_func, parameters):
    try:
        update_admin_task(
            task_id,
            status="running",
            started_at=True,
        )

        append_admin_task_log(task_id, "Task started.")

        def should_stop():
            return is_task_cancel_requested(task_id)

        result = job_func(
            task_id,
            parameters,
            should_stop=should_stop,
        )

        if is_task_cancel_requested(task_id):
            update_admin_task(
                task_id,
                status="cancelled",
                completed_at=True,
                result={"message": "Task đã được dừng bởi admin."},
            )
            append_admin_task_log(task_id, "Task cancelled by admin.")
            return

        if isinstance(result, dict) and result.get("status") == "cancelled":
            update_admin_task(
                task_id,
                status="cancelled",
                completed_at=True,
                result=result,
            )
            append_admin_task_log(task_id, "Task cancelled by admin.")
            return

        update_admin_task(
            task_id,
            status="completed",
            completed_at=True,
            result=result or {},
        )

        append_admin_task_log(task_id, "Task completed.")

    except Exception as error:
        if is_task_cancel_requested(task_id):
            update_admin_task(
                task_id,
                status="cancelled",
                completed_at=True,
                error="Task đã được dừng bởi admin.",
            )
            append_admin_task_log(task_id, "Task cancelled by admin.")
            return

        update_admin_task(
            task_id,
            status="failed",
            completed_at=True,
            error=str(error),
        )

        append_admin_task_log(task_id, f"Task failed: {str(error)}")


# ============================================================
# Background job functions
# ============================================================

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
        ),
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
                    "Admin requested crawler stop. Terminating crawler subprocess...",
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

                    important_keywords = [
                        "🚀", "🎯", "✅", "❌", "⚠️", "📊", "📦", "📁", "💾",
                        "CAPTCHA", "Slider", "Success", "Extracted", "saved",
                        "failed", "blocked", "Validation",
                    ]

                    if any(keyword in clean_line for keyword in important_keywords):
                        append_admin_task_log(task_id, clean_line)

            if process.poll() is not None:
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
                f"Crawler subprocess failed with code={return_code}",
            )

            if error_tail:
                append_admin_task_log(task_id, error_tail[-2500:])

            raise RuntimeError(
                error_tail or f"Crawler subprocess failed with code={return_code}"
            )

        append_admin_task_log(
            task_id,
            "Crawler subprocess completed successfully.",
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
        f"Starting YOLOv8 processing | batch_size={batch_size}, confidence={confidence}",
    )

    from ai.batch_vision_processor_final import FashionBatchProcessor

    processor = FashionBatchProcessor(model_path=model_path)

    try:
        result = processor.process_all_videos(
            batch_size=batch_size,
            conf=confidence,
            should_stop=should_stop,
        )

        processed_count = result.get("processed_count", 0) if isinstance(result, dict) else result

        append_admin_task_log(
            task_id,
            f"YOLOv8 processed {processed_count} videos.",
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
        f"Starting sync video stats | hours_gap={hours_gap}, limit={limit}",
    )

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
                should_stop=should_stop,
            )
        )

        append_admin_task_log(
            task_id,
            f"Sync video stats finished | result={result}",
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
        ),
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
            "Build trend_history completed.",
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
            f"Build trend_history failed: {str(e)}",
        )
        raise e

    finally:
        db_session.close()


def run_lstm_prediction_job(task_id: str, parameters: dict[str, Any], should_stop=None):
    raw_limit = parameters.get("limit")
    limit = int(raw_limit) if raw_limit not in [None, "", 0, "0"] else None

    append_admin_task_log(
        task_id,
        f"Running LSTM prediction | limit={limit or 'all'}",
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
        "message": "LSTM prediction completed.",
    }


def run_evaluate_predictions_job(task_id: str, parameters: dict[str, Any], should_stop=None):
    raw_limit = parameters.get("limit")
    limit = int(raw_limit) if raw_limit not in [None, "", 0, "0"] else None

    append_admin_task_log(
        task_id,
        f"Evaluating predictions | limit={limit or 'all'}",
    )

    from ai.prediction_evaluator import PredictionEvaluator

    evaluator = PredictionEvaluator()

    result = evaluator.evaluate_predictions(
        limit=limit,
        should_stop=should_stop,
    )

    append_admin_task_log(
        task_id,
        f"Evaluate predictions finished | result={result}",
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
            "message": "Backup đã được dừng bởi admin.",
        }

    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_prefix = "".join(
        char for char in file_prefix
        if char.isalnum() or char in ["_", "-"]
    ) or "backup"

    backup_file = backup_dir / f"{safe_prefix}_{timestamp}.sql"

    pg_dump_path = os.getenv("PG_DUMP_PATH") or shutil.which("pg_dump")

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
            str(backup_file),
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
            str(backup_file),
        ]

        if db_host:
            command.extend(["-h", db_host])

        if db_port:
            command.extend(["-p", db_port])

    append_admin_task_log(
        task_id,
        f"Creating database backup: {backup_file}",
    )

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    started = time.time()

    while process.poll() is None:
        if stop_requested():
            append_admin_task_log(task_id, "Admin requested backup stop. Terminating pg_dump...")
            process.terminate()

            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=10)

            return {
                "status": "cancelled",
                "message": "Backup đã được dừng bởi admin.",
            }

        if time.time() - started > timeout_seconds:
            process.kill()
            _, stderr = process.communicate(timeout=10)
            raise RuntimeError(stderr[-1500:] or "pg_dump timeout.")

        time.sleep(1)

    _, stderr = process.communicate(timeout=10)

    if process.returncode != 0:
        raise RuntimeError(stderr[-1500:] or "pg_dump failed.")

    return {
        "status": "completed",
        "backup_file": str(backup_file),
        "file_size_bytes": backup_file.stat().st_size if backup_file.exists() else 0,
        "message": "Database backup completed.",
    }
