"""
Integration Test - NLP + Vision (Phòng thí nghiệm)
"""
import logging
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.nlp_analyzer import NLPAnalyzer
from ai.vision_analyzer import FashionVisionAnalyzer

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def test_pipeline():
    logger.info("🔍 ĐANG KIỂM TRA HỆ THỐNG TÍCH HỢP...\n")

    # 1. Khởi tạo
    nlp = NLPAnalyzer()
    vision = FashionVisionAnalyzer()
    
    # 2. Giả lập dữ liệu đầu vào
    sample_text = "Mẫu áo sơ mi này phối với quần jeans rất hợp, vải mát."
    sample_image = "tests/sample_images/6.png" # Đảm bảo file này tồn tại để test thực tế
    
    print("-" * 40)
    # 3. Chạy NLP
    logger.info("📝 BƯỚC 1: PHÂN TÍCH NGÔN NGỮ (NLP)")
    nlp_res = nlp.analyze_text(sample_text)
    logger.info(f"-> Văn bản: '{sample_text}'")
    logger.info(f"-> Cảm xúc: {nlp_res['sentiment']} ({nlp_res['confidence']:.2f})")

    print("-" * 40)
    # 4. Chạy Vision (Nếu có file ảnh thực tế thì chạy thật)
    logger.info("🖼️ BƯỚC 2: PHÂN TÍCH HÌNH ẢNH (VISION)")
    if os.path.exists(sample_image):
        vision_res = vision.analyze_outfit(sample_image, conf=0.3)
        logger.info(f"-> Phát hiện: {vision_res['summary']}")
    else:
        logger.warning(f"-> ⚠️ Không tìm thấy ảnh {sample_image}, bỏ qua bước chạy thực tế.")
        vision_res = {'summary': 'shirt, jeans'} # Giả lập kết quả

    print("-" * 40)
    # 5. Kết luận tích hợp (Logic Đồ án)
    logger.info("💡 KẾT LUẬN HỆ THỐNG:")
    # Logic: Nếu người dùng khen (Positive) và AI thấy món đồ đó trong ảnh -> Xu hướng tốt
    is_match = "shirt" in vision_res['summary'].lower()
    
    if nlp_res['sentiment'] == 'POS' and is_match:
        logger.info("=> KẾT QUẢ: Xu hướng thời trang tích cực cho sản phẩm 'Shirt'.")
    
    logger.info("\n✅ KIỂM TRA TÍCH HỢP HOÀN TẤT!")

if __name__ == "__main__":
    test_pipeline()