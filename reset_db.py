from database.config import SessionLocal
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_database():
    db = SessionLocal()
    try:
        logger.info("⚠️ Đang bắt đầu xóa dữ liệu...")
        
        # Thứ tự xóa rất quan trọng vì các bảng có khóa ngoại (Foreign Keys)
        # Xóa bảng Stats và Hashtag_Video trước vì chúng tham chiếu đến Videos
        tables_to_truncate = [
            "video_stats",
            "video_hashtags", # Nếu bạn có bảng trung gian này
            "videos",
            "hashtags",
            "tiktok_users",
            "crawler_jobs"
        ]
        
        for table in tables_to_truncate:
            try:
                # TRUNCATE CASCADE sẽ xóa dữ liệu và các liên kết phụ thuộc
                db.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"))
                logger.info(f"✅ Đã xóa sạch bảng: {table}")
            except Exception as e:
                logger.warning(f"⚠️ Không thể xóa bảng {table}: {e}")
                db.rollback()

        db.commit()
        logger.info("✨ DATABASE ĐÃ TRỐNG - Bạn có thể bắt đầu thu thập lại từ đầu!")
        
    except Exception as e:
        logger.error(f"❌ Lỗi nghiêm trọng: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    confirm = input("Bạn có chắc chắn muốn XÓA TẤT CẢ dữ liệu không? (y/n): ")
    if confirm.lower() == 'y':
        reset_database()
    else:
        print("Hủy bỏ thao tác.")