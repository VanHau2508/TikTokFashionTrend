import logging
import random
from datetime import datetime, timedelta, timezone
from database.config import SessionLocal
from database.models import Video, Comment
import time
from sqlalchemy import func

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SmartCommentGenerator:
    """
    AI-Enhanced Comment Generator V2
    - Chống trùng lặp bằng Combinatorial Word Shuffling (Xáo trộn tổ hợp)
    - Cơ chế Incremental Scaling (Chỉ thêm phần còn thiếu)
    - Bộ từ vựng TikTok Style (Teencode, Slang, Icon)
    """
    
    def __init__(self):
        self.db = SessionLocal()
        
        # ======= NÂNG CẤP BỘ TỪ VỰNG (TIKTOK STYLE) =======
        self.pos_subjects = ["Áo này", "Váy này", "Set đồ", "Shop", "Sản phẩm", "Vải", "Form", "Màu này", "Outfit", "Đồ", "Mẫu này"]
        self.pos_adjectives = [
            "đẹp quá", "rất xịn", "xinh xỉu", "quá chất", "đáng mua", "rất hợp với mình", 
            "mặc lên tôn dáng", "cực kỳ ưng ý", "đỉnh vch", "xịn xò", "mlem mlem", 
            "đáng đồng tiền bát gạo", "không phí tiền", "ưng cái bụng", "tuyệt vời"
        ]
        self.pos_ends = ["nha mọi người", "luôn á", "❤️", "🔥", "💯", "uy tín luôn", "hihi", "đỉnh của chóp", "😍", "👌", "xịn nha"]

        self.neu_subjects = ["Shop ơi", "Cho mình", "Sản phẩm này", "Mẫu này", "Cao 1m6", "Ship", "Bạn ơi", "Admin ơi"]
        self.neu_actions = [
            "xin link mua", "hỏi giá với", "có size L không", "có màu khác không", 
            "bao lâu thì có hàng", "tư vấn mình với", "rep ib mình", "check dr shop ơi", 
            "đã đặt mong shop giao sớm", "màu ngoài có tối ko", "chất liệu gì vậy"
        ]
        self.neu_ends = ["ạ?", "vậy shop?", "...", "với", "nhỉ?", "được không?", "nha"]

        self.neg_subjects = ["Vải", "Giao hàng", "Giá", "Màu thực tế", "Form áo", "Hàng", "Shop làm ăn"]
        self.neg_issues = [
            "hơi mỏng", "hơi bị lâu", "mắc so với chất lượng", "không giống hình lắm", 
            "hơi thất vọng", "bị rộng quá", "hàng pha kè", "treo đầu dê bán thịt chó", 
            "vải chán đời", "mặc nóng như lò thiêu", "chán quá"
        ]
        self.neg_ends = ["😞", "😤", "quá đi", "thôi bỏ đi", "chán luôn", "haiz", "😠", "💔"]

    def _generate_text(self, sentiment):
        """Thuật toán xáo trộn cấu trúc để AI khôn hơn"""
        try:
            if sentiment == 'positive':
                s, a, e = random.choice(self.pos_subjects), random.choice(self.pos_adjectives), random.choice(self.pos_ends)
                # Ngẫu nhiên đảo thứ tự Subject và Adjective
                struct = random.choice([f"{s} {a} {e}", f"{a} {s} {e}", f"{s} {e} {a}"])
                return struct.strip()
            
            elif sentiment == 'neutral':
                s, ac, e = random.choice(self.neu_subjects), random.choice(self.neu_actions), random.choice(self.neu_ends)
                return f"{s} {ac} {e}".strip()
            
            else: # negative
                s, i, e = random.choice(self.neg_subjects), random.choice(self.neg_issues), random.choice(self.neg_ends)
                return f"{s} {i} {e}".strip()
        except Exception as e:
            return "Sản phẩm ok"

    def create_comments_list(self, video_id, num_comments):
        """Hàm chỉ tạo đối tượng, không lưu vào DB ngay"""
        comments_batch = []
        for _ in range(num_comments):
            rand = random.random()
            sentiment = 'positive' if rand < 0.60 else 'neutral' if rand < 0.85 else 'negative'
            content = self._generate_text(sentiment)
            comments_batch.append(Comment(
                video_id=video_id,
                commenter_id=f"user_{random.randint(100000, 999999)}",
                content=content,
                like_count=random.randint(0, 500),
                created_date=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30))
            ))
        return comments_batch

    def scale_up_database(self, target_per_video=15):
        logger.info(f"🚀 Chế độ BULK INSERT - Target: {target_per_video}")
        start_time = time.time()
        videos = self.db.query(Video).all()
        
        all_new_comments = [] # Chứa hàng ngàn comment để lưu một lần

        for idx, video in enumerate(videos, 1):
            current_count = self.db.query(Comment).filter(Comment.video_id == video.video_id).count()
            needed = target_per_video - current_count
            
            if needed > 0:
                # Gom objects vào danh sách tổng
                new_items = self.create_comments_list(video.video_id, needed)
                all_new_comments.extend(new_items)
            
            if idx % 50 == 0:
                logger.info(f"⏳ Đang xử lý logic cho video {idx}/{len(videos)}")

        # LƯU HÀNG LOẠT (Tốc độ cực nhanh)
        if all_new_comments:
            logger.info(f"📦 Đang đẩy {len(all_new_comments)} dòng vào Database...")
            self.db.bulk_save_objects(all_new_comments)
            self.db.commit()

        elapsed = time.time() - start_time
        logger.info(f"✨ HOÀN THÀNH! Thêm mới: {len(all_new_comments)} dòng trong {elapsed:.2f}s")
        self.db.close()

def main():
    generator = SmartCommentGenerator()
    
    # CHẾ ĐỘ NÂNG CẤP:
    # Bạn muốn mỗi video có 20 comments (Tổng ~12,000 dòng nếu có 600 videos)
    # Chạy lệnh này, video nào có 10 rồi nó sẽ chỉ thêm 10 nữa.
    # Video nào chưa có nó sẽ thêm đủ 20.
    generator.scale_up_database(target_per_video=15)

if __name__ == "__main__":
    main()