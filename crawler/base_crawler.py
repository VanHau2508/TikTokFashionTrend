from sqlalchemy.orm import Session
from database.models import (
    TikTokUser, Video, VideoStat, Hashtag, Comment, CrawlerJob, video_hashtags
)
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class BaseCrawler:
    """Base class for all crawlers"""
    
    def __init__(self, db: Session):
        self.db = db
        logger.info("Crawler initialized")
    
    # ====== TIKTOK USERS ======
    def upsert_tiktok_user(self, user_data):
        """Insert or update TikTok user"""
        
        try:
            unique_id = user_data.get('unique_id', '').strip()
            
            # ✅ FIX: Accept any non-empty ID (remove 'unknown' check for now)
            # If truly unknown, it won't pass JavaScript extraction
            if not unique_id or len(unique_id) < 2:
                logger.warning(f"⚠️  Invalid unique_id: '{unique_id}'")
                return None
            
            # Query by unique_id
            existing_user = self.db.query(TikTokUser).filter(
                TikTokUser.unique_id == unique_id
            ).first()
            
            if existing_user:
                # Update
                existing_user.nickname = user_data.get('nickname', unique_id)
                existing_user.last_updated = datetime.now(timezone.utc)
                self.db.commit()
                
                logger.debug(f"✅ User {unique_id} updated (ID: {existing_user.tiktok_user_id})")
                return existing_user.tiktok_user_id
            else:
                # Create new
                user = TikTokUser(
                    unique_id=unique_id,
                    nickname=user_data.get('nickname', unique_id),
                    created_at=datetime.now(timezone.utc)
                )
                self.db.add(user)
                self.db.commit()
                
                logger.debug(f"✅ User {unique_id} created (ID: {user.tiktok_user_id})")
                return user.tiktok_user_id
        
        except Exception as e:
            logger.error(f"Error upserting user {user_data.get('unique_id')}: {e}")
            self.db.rollback()
            return None
    
    # ====== VIDEOS ======
    def upsert_video(self, video_data, tiktok_user_id):
        """Insert or update video - ✅ FIX"""
        
        try:
            tiktok_video_id = video_data.get('video_id')
            
            if not tiktok_video_id:
                logger.warning("⚠️  Invalid video_id")
                return None
            
            # Query by tiktok_video_id
            existing_video = self.db.query(Video).filter(
                Video.tiktok_video_id == tiktok_video_id
            ).first()
            
            if existing_video:
                # Update
                existing_video.description = video_data.get('description', existing_video.description)
                existing_video.video_url = video_data.get('video_url', existing_video.video_url)
                existing_video.cover_url = video_data.get('cover_url', existing_video.cover_url)
                existing_video.tiktok_user_id = tiktok_user_id
                self.db.commit()
                
                logger.debug(f"✅ Video {tiktok_video_id} updated")
                return existing_video.video_id
            else:
                # Create new
                video = Video(
                    tiktok_video_id=tiktok_video_id,
                    tiktok_user_id=tiktok_user_id,
                    description=video_data.get('description', ''),
                    video_url=video_data.get('video_url', ''),
                    cover_url=video_data.get('cover_url', ''),
                    processing_status='pending', # Chờ AI xử lý (Vấn đề 3)
                    created_date=datetime.now(timezone.utc)
                )
                self.db.add(video)
                self.db.commit()
                
                logger.debug(f"✅ Video {tiktok_video_id} created (ID: {video.video_id})")
                return video.video_id
        
        except Exception as e:
            logger.error(f"Error upserting video {video_data.get('video_id')}: {e}")
            self.db.rollback()
            return None
    
    # ====== VIDEO STATS ======
    def insert_video_stats(self, video_id, stats):
        """Insert video stats - ✅ FIX"""
        try:
            # Check if stat already exists
            existing_stat = self.db.query(VideoStat).filter(
                VideoStat.video_id == video_id
            ).first()
            
            if existing_stat:
                # Update
                existing_stat.view_count = stats.get('view_count', 0)
                existing_stat.like_count = stats.get('like_count', 0)
                existing_stat.comment_count = stats.get('comment_count', 0)
                existing_stat.share_count = stats.get('share_count', 0)
                self.db.commit()
                logger.debug(f"✅ Stats for video {video_id} updated")
                return existing_stat.stat_id
            else:
                # Create new
                stat = VideoStat(
                    video_id=video_id,
                    view_count=stats.get('view_count', 0),
                    like_count=stats.get('like_count', 0),
                    comment_count=stats.get('comment_count', 0),
                    share_count=stats.get('share_count', 0)
                )
                self.db.add(stat)
                self.db.commit()
                logger.debug(f"✅ Stats for video {video_id} created")
                return stat.stat_id
            
        except Exception as e:
            logger.error(f"Error saving stats for video {video_id}: {e}")
            self.db.rollback()
            return None
    
    # ====== HASHTAGS ======
    def upsert_hashtag(self, tag_name, category=None):
        """Insert or update hashtag - ✅ FIX"""
        try:
            tag_name = tag_name.lower().strip()
            
            if not tag_name:
                return None
            
            hashtag = self.db.query(Hashtag).filter(
                Hashtag.tag_name == tag_name
            ).first()
            
            if hashtag:
                hashtag.last_seen = datetime.now(timezone.utc)

                if category:
                    hashtag.category = category

                self.db.commit()
                return hashtag.hashtag_id
            else:
                hashtag = Hashtag(
                    tag_name=tag_name,
                    category=category or 'general',
                    first_seen=datetime.now(timezone.utc),
                    last_seen=datetime.now(timezone.utc)
                )
                self.db.add(hashtag)
                self.db.commit()
                logger.debug(f"✅ Hashtag {tag_name} created (ID: {hashtag.hashtag_id})")
                return hashtag.hashtag_id
            
        except Exception as e:
            logger.error(f"Error saving hashtag {tag_name}: {e}")
            self.db.rollback()
            return None
    
    # ====== COMMENTS ======
    def insert_comment(self, video_id, comment_data):
        """Insert comment - ✅ FIX"""
        try:
            comment = Comment(
                video_id=video_id,
                commenter_id=comment_data.get('commenter_id', 'unknown'),
                content=comment_data.get('content', ''),
                like_count=comment_data.get('like_count', 0),
                created_date=comment_data.get('created_date', datetime.now(timezone.utc))
            )
            self.db.add(comment)
            self.db.commit()
            logger.debug(f"✅ Comment created (ID: {comment.comment_id})")
            return comment.comment_id
            
        except Exception as e:
            logger.error(f"Error saving comment: {e}")
            self.db.rollback()
            return None
    
    # ====== CRAWLER JOBS ======
    def create_crawler_job(self, job_name, job_type, parameters, created_by=1):
        """Create crawler job record - ✅ FIX"""
        try:
            job = CrawlerJob(
                job_name=job_name,
                job_type=job_type,
                parameters=parameters,
                status='running',
                created_by=created_by,
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(job)
            self.db.commit()
            logger.info(f"✅ Crawler job {job.job_id} created: {job_name}")
            return job.job_id
            
        except Exception as e:
            logger.error(f"Error creating job: {e}")
            self.db.rollback()
            return None
    
    def update_crawler_job(self, job_id, status, videos_collected=None, error_message=None):
        """Update crawler job - ✅ FIX"""
        try:
            job = self.db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
            
            if job:
                job.status = status
                if videos_collected is not None:
                    job.videos_collected = videos_collected
                if error_message:
                    job.error_message = error_message
                if status in ['completed', 'failed']:
                    job.completed_at = datetime.now(timezone.utc)
                
                self.db.commit()
                logger.info(f"✅ Job {job_id} updated: {status}")
            else:
                logger.warning(f"⚠️  Job {job_id} not found")
            
        except Exception as e:
            logger.error(f"Error updating job: {e}")
            self.db.rollback()
    def link_video_hashtag(self, video_id, hashtag_id):
        """Link video to hashtag - Đã sửa lỗi 'Table' object"""
        try:
            # 1. Sử dụng .c. để truy cập các cột video_id và hashtag_id
            # Lưu ý: video_hashtags.c.video_id thay vì video_hashtags.video_id
            existing_link = self.db.query(video_hashtags).filter(
                video_hashtags.c.video_id == video_id,
                video_hashtags.c.hashtag_id == hashtag_id
            ).first()
            
            if not existing_link:
                # 2. Vì là Table object, không dùng self.db.add(link)
                # Hãy dùng phương thức insert() của Table
                stmt = video_hashtags.insert().values(
                    video_id=video_id,
                    hashtag_id=hashtag_id
                )
                self.db.execute(stmt)
                self.db.commit()
                
                logger.debug(f"✅ Video {video_id} linked to hashtag {hashtag_id}")
                return True
            
            return True
            
        except Exception as e:
            # Nếu gặp lỗi "duplicate key", commit bị lỗi thì rollback
            logger.error(f"Error linking video-hashtag: {e}")
            self.db.rollback()
            return False
     
    def check_video_exists(self, tiktok_video_id):
        """Kiểm tra xem video đã tồn tại dựa trên ID của TikTok chưa"""
        try:
            # Lưu ý: Video.tiktok_video_id là ID từ TikTok (chuỗi số dài)
            exists = self.db.query(Video.video_id).filter(
                Video.tiktok_video_id == str(tiktok_video_id)
            ).first()
            return exists is not None
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra video tồn tại: {e}")
            return False