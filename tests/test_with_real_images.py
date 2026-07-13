import logging
import sys
import os
import cv2
import argparse
from pathlib import Path

# Thêm đường dẫn gốc để import được module ai
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.vision_analyzer import FashionVisionAnalyzer

# Cấu hình Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RealImageTester:
    """Bộ kiểm thử nhận diện thời trang trên ảnh thực tế"""
    
    def __init__(self):
        logger.info("🚀 Đang khởi tạo Vision Analyzer...")
        self.analyzer = FashionVisionAnalyzer()
        logger.info("✅ Hệ thống đã sẵn sàng!\n")
    
    def visualize_detections(self, image_path, detections, output_dir="tests/results"):
        """Vẽ khung nhận diện và lưu ảnh"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        img = cv2.imread(image_path)
        if img is None:
            return None

        for item in detections:
            bbox = item['bbox']
            # Tạo nhãn: Tên món đồ + % tin cậy
            label = f"{item['full_name']} ({item['confidence']:.2f})"
            
            x1, y1, x2, y2 = map(int, bbox)
            
            # Vẽ khung màu xanh lá (BGR: 0, 255, 0)
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Vẽ nền cho chữ để dễ đọc hơn
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(img, (x1, y1 - 20), (x1 + w, y1), (0, 255, 0), -1)
            
            # Ghi chữ lên ảnh
            cv2.putText(img, label, (x1, y1 - 5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        output_path = os.path.join(output_dir, os.path.basename(image_path))
        cv2.imwrite(output_path, img)
        return output_path

    def test_batch_images(self, image_dir, conf=0.25):
        """Quét toàn bộ thư mục ảnh và phân tích"""
        image_dir = Path(image_dir)
        
        if not image_dir.exists():
            logger.error(f"❌ Không tìm thấy thư mục: {image_dir}")
            return
        
        # Lấy tất cả ảnh (hỗ trợ cả đuôi hoa và thường)
        extensions = ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.PNG']
        images = []
        for ext in extensions:
            images.extend(list(image_dir.glob(ext)))
        
        if not images:
            logger.warning(f"⚠️ Không tìm thấy file ảnh nào trong {image_dir}")
            return
        
        logger.info(f"🔄 Đang kiểm tra {len(images)} ảnh với độ tin cậy >= {conf}\n")
        
        results = []
        for idx, image_path in enumerate(images, 1):
            img_str = str(image_path)
            logger.info(f"[{idx}/{len(images)}] Đang xử lý: {image_path.name}")
            
            # Thực hiện nhận diện
            items = self.analyzer.detect_fashion_items(img_str, conf=conf)
            outfit = self.analyzer.analyze_outfit(img_str, conf=conf)
            
            # Vẽ và lưu kết quả trực quan
            saved_path = self.visualize_detections(img_str, items)
            
            results.append({
                'image': image_path.name,
                'total': outfit['total_items'],
                'summary': outfit['summary'],
                'path': saved_path
            })
            
            logger.info(f"   → Phát hiện: {outfit['summary']}")
            if saved_path:
                logger.info(f"   → Đã lưu ảnh tại: {saved_path}\n")

        # In bảng tổng kết cuối cùng
        print("\n" + "="*50)
        print(f"{'IMAGE':<20} | {'ITEMS':<5} | {'SUMMARY'}")
        print("-" * 50)
        for r in results:
            print(f"{r['image']:<20} | {r['total']:<5} | {r['summary']}")
        print("="*50 + "\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', action='store_true', help='Chạy test toàn bộ thư mục sample_images')
    parser.add_argument('--conf', type=float, default=0.25, help='Độ tự tin tối thiểu (0.1 - 1.0)')
    args = parser.parse_args()

    tester = RealImageTester()
    
    # Mặc định chạy batch nếu không truyền tham số khác
    sample_dir = "tests/sample_images"
    tester.test_batch_images(sample_dir, conf=args.conf)

if __name__ == "__main__":
    main()