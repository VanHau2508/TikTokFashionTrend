import logging
import re
from database.config import SessionLocal
from database.models import Video, Hashtag, video_hashtags
from sqlalchemy import insert, select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_hashtags_from_videos():
    logger.info("="*70)
    logger.info("🏷️  EXTRACTING HASHTAGS FROM VIDEOS (FIXED)")
    logger.info("="*70 + "\n")
    
    db = SessionLocal()
    
    try:
        videos = db.query(Video).all()
        logger.info(f"📹 Scanning {len(videos)} videos\n")
        
        hashtags_created = 0
        links_created = 0
        
        for idx, video in enumerate(videos, 1):
            if idx <= 5:
                logger.info(f"🔍 DEBUG Video {video.video_id} Desc: '{video.description}'")
            if not video.description:
                continue

            # Regex cải tiến: Lấy hashtag bao gồm cả tiếng Việt có dấu
            # Loại bỏ dấu # ở đầu để lấy tên tag
            tags = re.findall(r'#([^\s#@,.]+)', video.description)
            
            if tags:
                # Debug nhỏ để bạn thấy script đang thực sự tìm thấy gì
                # logger.info(f"Found in Video {video.video_id}: {tags}") 
                pass

            for tag_name in tags:
                tag_name = tag_name.lower().strip()
                if not tag_name: continue

                # 1. Xử lý bảng Hashtag (ORM)
                hashtag = db.query(Hashtag).filter(Hashtag.tag_name == tag_name).first()
                if not hashtag:
                    hashtag = Hashtag(tag_name=tag_name, category='general')
                    db.add(hashtag)
                    db.flush() # Để có hashtag_id ngay lập tức
                    hashtags_created += 1

                # 2. Xử lý bảng trung gian video_hashtags (Core)
                # Kiểm tra tồn tại bằng lệnh select của Core
                check_stmt = select(video_hashtags).where(
                    video_hashtags.c.video_id == video.video_id,
                    video_hashtags.c.hashtag_id == hashtag.hashtag_id
                )
                existing_link = db.execute(check_stmt).first()

                if not existing_link:
                    # Dùng db.execute thay vì db.add cho Table object
                    stmt = insert(video_hashtags).values(
                        video_id=video.video_id,
                        hashtag_id=hashtag.hashtag_id
                    )
                    db.execute(stmt)
                    links_created += 1
            
            # Commit theo từng video để đảm bảo an toàn dữ liệu
            if idx % 10 == 0:
                db.commit()
                
            if idx % 100 == 0:
                logger.info(f"✅ Processed {idx}/{len(videos)} videos")
        
        db.commit() # Final commit
        
        logger.info(f"\n{'='*70}")
        logger.info(f"✅ HASHTAGS EXTRACTION COMPLETE")
        logger.info(f"   Hashtags created: {hashtags_created}")
        logger.info(f"   Links created: {links_created}")
        logger.info(f"{'='*70}\n")
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    extract_hashtags_from_videos()