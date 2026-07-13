from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from backend.security import require_admin
from database.models import CrawlerJob

router = APIRouter(prefix="/api/admin", tags=["Admin Jobs"])


@router.get("/crawler-jobs")
def get_crawler_jobs(
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    jobs = db.query(CrawlerJob).order_by(
        desc(CrawlerJob.created_at)
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
            "created_at": job.created_at,
        }
        for job in jobs
    ]
