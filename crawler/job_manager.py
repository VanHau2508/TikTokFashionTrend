from datetime import timezone
from database.config import SessionLocal
from database.models import CrawlerJob
from loguru import logger
import json

class CrawlerJobManager:
    """Manage crawler jobs"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    def create_job(self, job_name, job_type, parameters, created_by=1):
        """Create new job"""
        try:
            job = CrawlerJob(
                job_name=job_name,
                job_type=job_type,
                parameters=parameters,
                status='pending',
                created_by=created_by
            )
            self.db.add(job)
            self.db.commit()
            
            logger.info(f"✅ Created job {job.job_id}: {job_name}")
            return job.job_id
            
        except Exception as e:
            logger.error(f"❌ Error creating job: {e}")
            self.db.rollback()
            return None
    
    def update_job_status(self, job_id, status, videos_collected=None, error_message=None):
        """Update job status"""
        try:
            job = self.db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
            
            if job:
                job.status = status
                if videos_collected is not None:
                    job.videos_collected = videos_collected
                if error_message:
                    job.error_message = error_message
                
                from datetime import datetime
                if status in ['completed', 'failed']:
                    job.completed_at = datetime.now(timezone.utc)
                
                self.db.commit()
                logger.info(f"✅ Job {job_id} status: {status}")
            
        except Exception as e:
            logger.error(f"❌ Error updating job: {e}")
            self.db.rollback()
    
    def get_pending_jobs(self):
        """Get all pending jobs"""
        return self.db.query(CrawlerJob).filter(
            CrawlerJob.status == 'pending'
        ).all()
    
    def close(self):
        self.db.close()

# Usage
if __name__ == "__main__":
    manager = CrawlerJobManager()
    job_id = manager.create_job(
        job_name="Test crawl",
        job_type="hashtag",
        parameters={"hashtag": "thờitrang", "max_videos": 50}
    )
    logger.info(f"Created job: {job_id}")
    manager.close()