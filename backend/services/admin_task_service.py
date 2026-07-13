from datetime import datetime, timezone
from database.config import SessionLocal
from database.models import AdminTask


def create_admin_task(task_type, title, parameters=None):
    db = SessionLocal()
    try:
        task = AdminTask(
            task_type=task_type,
            title=title,
            status="pending",
            parameters=parameters or {},
            logs=[]
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task.task_id
    finally:
        db.close()


def append_task_log(task_id, message):
    db = SessionLocal()
    try:
        task = db.query(AdminTask).filter(AdminTask.task_id == task_id).first()
        if not task:
            return

        logs = task.logs or []
        logs.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "message": message
        })

        task.logs = logs
        db.commit()
    finally:
        db.close()


def update_task_status(task_id, status, result=None, error_message=None):
    db = SessionLocal()
    try:
        task = db.query(AdminTask).filter(AdminTask.task_id == task_id).first()
        if not task:
            return

        task.status = status

        if status == "running":
            task.started_at = datetime.now(timezone.utc)

        if status in ["completed", "failed"]:
            task.completed_at = datetime.now(timezone.utc)

        if result is not None:
            task.result = result

        if error_message:
            task.error_message = error_message

        db.commit()
    finally:
        db.close()