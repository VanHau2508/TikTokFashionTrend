import torch
import functools
import logging
import os
from ultralytics import YOLO

# Fix bảo mật PyTorch 2.6
_original_torch_load = torch.load
torch.load = functools.partial(_original_torch_load, weights_only=False)

from ai.fashion_taxonomy import (
    get_item_by_class_name,
    get_category_by_class_name,
    get_class_names_list
)

logger = logging.getLogger(__name__)

class FashionVisionAnalyzer:
    def __init__(self, model_path='ai/models/yolov8m_fashion_best.pt'):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"❌ Không thấy model: {model_path}")

        try:
            self.model = YOLO(model_path)
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.model.to(self.device)
            
            # Lấy tên các class trực tiếp từ model training
            self.model_classes = self.model.names 
            logger.info(f"✅ Vision Analyzer ready on {self.device}")
        except Exception as e:
            logger.error(f"❌ Lỗi khởi tạo: {e}")
            raise e
    
    def detect_fashion_items(self, image_path, conf=0.25):
        try:
            results = self.model.predict(source=image_path, conf=conf, verbose=False)
            result = results[0]
            detected_items = []
            
            for box in result.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                bbox = box.xyxy[0].tolist()
                
                # Lấy tên từ model (ví dụ: 'shirt')
                yolo_name = self.model_classes[class_id]
                
                # Tra cứu thông tin chi tiết
                item_details = get_item_by_class_name(yolo_name)
                category = get_category_by_class_name(yolo_name)
                
                detected_items.append({
                    'class_id': class_id,
                    'class_name': yolo_name,
                    'category': category,
                    'full_name': item_details['name'] if item_details else yolo_name,
                    'confidence': round(confidence, 4),
                    'bbox': [round(x, 2) for x in bbox]
                })
            return detected_items
        except Exception as e:
            logger.error(f"Lỗi detection: {e}")
            return []

    def analyze_outfit(self, image_path, conf=0.25):
        items = self.detect_fashion_items(image_path, conf)
        outfit = {
            'tops': [], 'outerwear': [], 'bottoms': [], 
            'dresses': [], 'footwear': [], 'accessories': [],
            'total_items': len(items), 'summary': ""
        }
        for item in items:
            cat = item['category']
            if cat in outfit: outfit[cat].append(item)
        
        parts = [f"{len(outfit[k])} {k}" for k in outfit if isinstance(outfit[k], list) and outfit[k]]
        outfit['summary'] = ", ".join(parts) if parts else "No items detected"
        return outfit