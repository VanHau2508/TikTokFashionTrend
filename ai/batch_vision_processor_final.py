import logging
import sys
import os
import cv2
import tempfile
import subprocess
import unicodedata
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# Import các model từ hệ thống của bạn
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.config import SessionLocal
from database.models import Video, AIAnalysis, FashionItem
from ai.vision_analyzer import FashionVisionAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# DB hiện tại có CHECK constraint cho ai_analysis.analysis_type.
# Giá trị "fashion_relevance" có thể chưa được cho phép trong PostgreSQL,
# nên dùng "vision" để tương thích DB cũ; loại phân tích thật lưu trong result_json.
AI_ANALYSIS_TYPE_FOR_DB = "vision"
AI_RESULT_KIND = "fashion_relevance"


# Các nhóm YOLO output đang dùng trong FashionVisionAnalyzer
FASHION_CATEGORIES = [
    'tops',
    'outerwear',
    'bottoms',
    'dresses',
    'footwear',
    'accessories',
]

# Nhóm item có giá trị xác nhận thời trang mạnh hơn.
# Lưu ý: dùng đúng yolo_class trong fashion_taxonomy của bạn.
STRONG_FASHION_ITEMS = {
    'shirt', 't_shirt', 'polo_shirt', 'crop_top',
    'jacket', 'hoodie', 'cardigan', 'blazer',
    'shorts', 'jeans', 'pants', 'skirt', 'dress',
    'sneakers', 'formal_shoes', 'slippers',
    'bags', 'backpack', 'watch', 'cap', 'sunglasses',
}

# Tín hiệu chữ giúp tăng độ chắc chắn rằng video thuộc ngữ cảnh thời trang
FASHION_TEXT_KEYWORDS = {
    'fashion', 'style', 'outfit', 'ootd', 'streetwear', 'y2k', 'vintage',
    'menswear', 'womenswear', 'lookbook', 'fitcheck', 'fit check',
    'phoi do', 'phối đồ', 'mac dep', 'mặc đẹp', 'thoi trang', 'thời trang',
    'ao', 'áo', 'quan', 'quần', 'vay', 'váy', 'dam', 'đầm',
    'giay', 'giày', 'sneaker', 'sneakers', 'tui', 'túi', 'non', 'nón', 'mu', 'mũ',
    'aokhoac', 'áo khoác', 'hoodie', 'jacket', 'jeans', 'chan vay', 'chân váy',
}

# Tín hiệu chữ cảnh báo nội dung có thể không liên quan thời trang
NON_FASHION_KEYWORDS = {
    'ga', 'gà', 'vit', 'vịt', 'heo', 'lợn', 'bo', 'bò',
    'nau an', 'nấu ăn', 'do an', 'đồ ăn', 'mon ngon', 'món ngon', 'an uong', 'ăn uống',
    'game', 'gaming', 'lien quan', 'liên quân', 'free fire', 'valorant', 'pubg',
    'hai', 'hài', 'nhac', 'nhạc', 'lyrics', 'karaoke', 'remix',
    'bong da', 'bóng đá', 'football', 'messi', 'ronaldo',
    'meo', 'mèo', 'cho', 'chó', 'pet', 'cat', 'dog',
    'phim', 'movie', 'review phim', 'tin tuc', 'tin tức', 'thoi su', 'thời sự',
}


class FashionBatchProcessor:
    def __init__(self, model_path='ai/models/yolov8m_fashion_best.pt'):
        logger.info("🧥 Khởi tạo hệ thống xử lý Video Batch + Fashion Relevance Filter...")
        try:
            self.db = SessionLocal()
            self.analyzer = FashionVisionAnalyzer(model_path)
            self.model_id = 2
            logger.info("✅ Hệ thống đã sẵn sàng!")
        except Exception as e:
            logger.error(f"❌ Lỗi khởi tạo: {e}")
            raise

    def _normalize_text(self, text):
        """Chuẩn hóa text để bắt keyword cả có dấu và không dấu."""
        if not text:
            return ""
        text = str(text).lower().strip()
        no_accent = ''.join(
            ch for ch in unicodedata.normalize('NFD', text)
            if unicodedata.category(ch) != 'Mn'
        )
        # Ghép cả bản có dấu và không dấu để keyword nào cũng match được
        return f"{text} {no_accent}"

    def _safe_json_value(self, value):
        """Đảm bảo dữ liệu lưu JSONB không bị lỗi kiểu numpy/tuple."""
        if value is None:
            return None
        if hasattr(value, 'tolist'):
            return value.tolist()
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, list):
            return [self._safe_json_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._safe_json_value(v) for k, v in value.items()}
        try:
            # numpy float/int thường ép được về float/int
            if isinstance(value, float):
                return float(value)
            if isinstance(value, int):
                return int(value)
        except Exception:
            pass
        return value

    def _build_adaptive_timestamps(self, duration_seconds):
        """
        Tạo danh sách mốc thời gian lấy frame theo độ dài video.

        Mục tiêu:
        - Video ngắn: lấy dày hơn để không bỏ lỡ outfit.
        - Video dài: không lấy quá nhiều frame để tránh chậm và tránh làm giảm score.
        - Không lấy sát đầu/cuối vì TikTok thường có intro/outro/text overlay.
        """
        if not duration_seconds or duration_seconds <= 0:
            return [2000, 4000, 6000, 8000, 10000]

        duration_seconds = float(duration_seconds)

        # Video rất ngắn thì bắt đầu sớm hơn một chút.
        if duration_seconds <= 3:
            start = 0.5
            end = max(0.8, duration_seconds - 0.3)
        else:
            start = max(1.0, duration_seconds * 0.10)
            end = min(duration_seconds - 0.5, duration_seconds * 0.90)

        if end <= start:
            end = duration_seconds

        # Số frame tối đa theo độ dài video.
        # Không lấy từng giây toàn bộ video dài vì sẽ chậm và có thể làm score bị loãng.
        if duration_seconds <= 8:
            step = 1.0
            times = []
            t = start
            while t <= end:
                times.append(t)
                t += step
        elif duration_seconds <= 15:
            n = 8
            times = [start + i * (end - start) / max(1, n - 1) for i in range(n)]
        elif duration_seconds <= 30:
            n = 10
            times = [start + i * (end - start) / max(1, n - 1) for i in range(n)]
        else:
            n = 12
            times = [start + i * (end - start) / max(1, n - 1) for i in range(n)]

        timestamps_ms = []
        seen = set()
        for t in times:
            ts = int(max(0.1, min(t, duration_seconds)) * 1000)
            # làm tròn nhẹ để hạn chế trùng mốc
            ts = int(round(ts / 100.0) * 100)
            if ts not in seen:
                seen.add(ts)
                timestamps_ms.append(ts)

        return sorted(timestamps_ms)

    def extract_multiple_frames(self, tiktok_web_url, timestamps_ms=None, should_stop=None):
        """
        Tải video TikTok và trích xuất frame thích ứng theo độ dài video.

        Nếu timestamps_ms được truyền vào thì dùng danh sách đó.
        Nếu không truyền vào thì tự đọc duration của video và tạo mốc frame hợp lý.
        """
        temp_dir = tempfile.gettempdir()
        temp_video_path = os.path.join(temp_dir, f"temp_vid_{datetime.now().timestamp()}.mp4")
        frame_paths = []

        def stop_requested():
            return should_stop is not None and should_stop()

        if stop_requested():
            logger.warning("🛑 Admin đã yêu cầu dừng trước khi tải video.")
            return []

        if not tiktok_web_url:
            logger.warning("⚠️ Video không có URL để xử lý.")
            return []

        try:
            # 1. Tải video tạm thời.
            # --merge-output-format mp4 giúp đầu ra ổn định hơn khi yt-dlp chọn format khác.
            cmd = [
                'yt-dlp',
                '-o', temp_video_path,
                '-f', 'mp4/best[ext=mp4]/best',
                '--merge-output-format', 'mp4',
                '--limit-rate', '1M',
                '--no-playlist',
                tiktok_web_url,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"   ⚠️ yt-dlp tải video thất bại: {(result.stderr or result.stdout or '')[:300]}")
                return []

            if not os.path.exists(temp_video_path):
                logger.warning("   ⚠️ Không tìm thấy file video sau khi tải.")
                return []

            if stop_requested():
                logger.warning("🛑 Admin đã yêu cầu dừng sau khi tải video.")
                return []

            # 2. Mở video và tính duration.
            cap = cv2.VideoCapture(temp_video_path)
            if not cap.isOpened():
                logger.warning("   ⚠️ OpenCV không mở được video.")
                return []

            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            frame_total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            duration_seconds = (frame_total / fps) if fps and fps > 0 else 0

            if timestamps_ms is None:
                timestamps_ms = self._build_adaptive_timestamps(duration_seconds)

            logger.info(
                f"   🎞️ Duration≈{duration_seconds:.2f}s | "
                f"frames_to_extract={len(timestamps_ms)} | "
                f"timestamps_ms={timestamps_ms}"
            )

            # 3. Lấy frame tại các mốc đã chọn.
            for ts in timestamps_ms:
                if stop_requested():
                    logger.warning("🛑 Admin đã yêu cầu dừng khi đang trích xuất frame.")
                    break

                # Không seek vượt quá duration để hạn chế read fail ở cuối video.
                if duration_seconds and ts > int(duration_seconds * 1000):
                    continue

                cap.set(cv2.CAP_PROP_POS_MSEC, ts)
                success, frame = cap.read()
                if success and frame is not None:
                    f_name = os.path.join(temp_dir, f"frame_{ts}_{datetime.now().timestamp()}.jpg")
                    cv2.imwrite(f_name, frame)
                    frame_paths.append(f_name)
                    logger.info(f"   📸 Đã lấy frame tại {ts}ms")

            cap.release()
            return frame_paths

        except Exception as e:
            logger.error(f"   ⚠️ Lỗi trích xuất đa khung hình: {e}")
            return []
        finally:
            if os.path.exists(temp_video_path):
                try:
                    os.remove(temp_video_path)
                except Exception:
                    pass

    def _extract_items_from_outfit(self, outfit, frame_index):
        """Chuẩn hóa output từ FashionVisionAnalyzer thành danh sách item lưu được vào DB/JSONB."""
        frame_items = []

        for category in FASHION_CATEGORIES:
            for item in outfit.get(category, []):
                detected_label = item.get('class_name')

                if not detected_label or detected_label == 'unknown':
                    continue

                try:
                    confidence = float(item.get('confidence', 0) or 0)
                except Exception:
                    confidence = 0.0

                frame_items.append({
                    "frame_index": frame_index,
                    "category": category,
                    "item_type": str(detected_label).strip().lower(),
                    "confidence": confidence,
                    # FashionItem.bbox là JSONB nên lưu list/dict trực tiếp, không json.dumps
                    "bbox": self._safe_json_value(item.get('bbox', [])),
                })

        return frame_items

    def classify_fashion_relevance(self, video, frame_results, frame_count):
        """
        Phân loại video có đủ liên quan thời trang hay không.

        Mục tiêu: tăng Precision để tránh đưa video rác vào trend_history/LSTM.
        Return: (decision_status, relevance_score, reason, metrics)
        """
        description_norm = self._normalize_text(getattr(video, 'description', '') or '')

        all_items = [item for frame_items in frame_results for item in frame_items]
        detected_frames = sum(1 for frame_items in frame_results if len(frame_items) > 0)

        if frame_count <= 0:
            return "failed_no_frame", 0.0, "Không trích xuất được frame", {
                "frame_count": 0,
                "detected_frame_count": 0,
                "total_detected_items": 0,
            }

        if not all_items:
            return "failed_no_fashion", 0.0, "YOLO không phát hiện item thời trang", {
                "frame_count": frame_count,
                "detected_frame_count": 0,
                "total_detected_items": 0,
            }

        avg_conf = sum(item["confidence"] for item in all_items) / max(1, len(all_items))
        strong_item_count = sum(
            1 for item in all_items
            if item["item_type"] in STRONG_FASHION_ITEMS
        )

        positive_text_hits = sum(
            1 for word in FASHION_TEXT_KEYWORDS
            if self._normalize_text(word) in description_norm
        )
        negative_text_hits = sum(
            1 for word in NON_FASHION_KEYWORDS
            if self._normalize_text(word) in description_norm
        )

        # Điểm tổng 0-100.
        # Bản cũ dùng detected_frames / frame_count nên video dài bị phạt khi lấy nhiều frame.
        # Bản mới: chỉ cần phát hiện ổn ở một số frame đại diện là đủ điểm.
        detection_score = min(35.0, detected_frames * 8.0)
        item_score = min(25.0, strong_item_count * 5.0)
        confidence_score = min(20.0, avg_conf * 20.0)
        text_score = min(15.0, positive_text_hits * 5.0)
        negative_penalty = min(35.0, negative_text_hits * 15.0)

        score = detection_score + item_score + confidence_score + text_score - negative_penalty
        score = max(0.0, min(100.0, score))

        # Yêu cầu ít nhất 1 frame có item. Nếu lấy nhiều frame, 2 frame là tốt hơn.
        min_detected_frames = 2 if frame_count >= 6 else 1
        min_strong_items = 1

        metrics = {
            "frame_count": frame_count,
            "detected_frame_count": detected_frames,
            "total_detected_items": len(all_items),
            "strong_item_count": strong_item_count,
            "avg_confidence": avg_conf,
            "positive_text_hits": positive_text_hits,
            "negative_text_hits": negative_text_hits,
            "detection_score": detection_score,
            "item_score": item_score,
            "confidence_score": confidence_score,
            "text_score": text_score,
            "negative_penalty": negative_penalty,
            "min_detected_frames_required": min_detected_frames,
            "min_strong_items_required": min_strong_items,
        }

        if (
            score >= 60.0
            and detected_frames >= min_detected_frames
            and strong_item_count >= min_strong_items
            and negative_text_hits == 0
        ):
            return "success", score, "Video đủ điều kiện thời trang", metrics

        if (
            score >= 50.0
            and strong_item_count >= 1
            and avg_conf >= 0.55
            and negative_text_hits == 0
            and (
                detected_frames >= 2
                or positive_text_hits >= 2
            )
        ):
            return "success", score, "Video đủ điều kiện thời trang mức mở rộng", metrics

        if score >= 45.0:
            return "uncertain", score, "Video có dấu hiệu thời trang nhưng chưa đủ chắc chắn", metrics

        return "failed_no_fashion", score, "Video không đủ điều kiện thời trang", metrics

    def _save_ai_analysis(self, video_id, decision_status, relevance_score, reason, metrics, detected_items=None):
        """Lưu kết quả kiểm định liên quan thời trang vào ai_analysis."""
        analysis = AIAnalysis(
            video_id=video_id,
            model_id=self.model_id,
            analysis_type=AI_ANALYSIS_TYPE_FOR_DB,
            result_json={
                "result_kind": AI_RESULT_KIND,
                "decision": decision_status,
                "fashion_relevance_score": relevance_score,
                "reason": reason,
                "metrics": metrics,
                "detected_items": detected_items or [],
            },
            confidence_score=float(relevance_score) / 100.0
        )
        self.db.add(analysis)

    def process_all_videos(self, batch_size=20, conf=0.35, should_stop=None):
        total_processed = 0

        def stop_requested():
            return should_stop is not None and should_stop()

        while True:
            if stop_requested():
                logger.warning("🛑 YOLO processing đã bị dừng bởi admin.")
                return {
                    "status": "cancelled",
                    "processed_count": total_processed,
                    "message": "Task đã được dừng bởi admin."
                }

            # Chỉ xử lý video trong phạm vi nghiên cứu 2026 và chưa qua AI filtering.
            # Video out_scope vẫn giữ trong DB nhưng không đưa vào YOLO/trend pipeline.
            videos = self.db.query(Video).filter(
                Video.is_in_scope == True,
                Video.processing_status == 'pending',
                Video.is_analyzed == False
            ).order_by(Video.published_at.desc()).limit(batch_size).all()

            if not videos:
                logger.info("🎉 Đã quét xong toàn bộ danh sách pending!")
                break

            for video in videos:
                # Lưu ID dạng biến thường để sau lỗi commit/rollback không bị PendingRollbackError
                current_video_id = getattr(video, "video_id", None)
                current_tiktok_video_id = getattr(video, "tiktok_video_id", None)

                if stop_requested():
                    logger.warning("🛑 Admin đã yêu cầu dừng YOLO processing.")
                    return {
                        "status": "cancelled",
                        "processed_count": total_processed,
                        "message": "Task đã được dừng bởi admin."
                    }

                frame_paths = []
                try:
                    url_to_process = video.video_url if video.video_url else video.cover_url
                    logger.info(f"📹 Đang xử lý ID: {current_video_id} - {current_tiktok_video_id}")

                    frame_paths = self.extract_multiple_frames(url_to_process, should_stop=should_stop)

                    if not frame_paths:
                        logger.warning("   ⏩ Không lấy được frame. Đánh dấu failed_no_frame.")
                        video.processing_status = 'failed_no_frame'
                        video.is_analyzed = True
                        self._save_ai_analysis(
                            video_id=video.video_id,
                            decision_status='failed_no_frame',
                            relevance_score=0.0,
                            reason='Không tải được video hoặc không trích xuất được frame',
                            metrics={
                                "frame_count": 0,
                                "detected_frame_count": 0,
                                "total_detected_items": 0,
                            },
                            detected_items=[]
                        )
                        self.db.commit()
                        total_processed += 1
                        continue

                    frame_results = []

                    for frame_index, f_path in enumerate(frame_paths):
                        if stop_requested():
                            logger.warning("🛑 Admin đã yêu cầu dừng khi đang phân tích frame.")
                            return {
                                "status": "cancelled",
                                "processed_count": total_processed,
                                "message": "Task đã được dừng bởi admin."
                            }

                        outfit = self.analyzer.analyze_outfit(f_path, conf=conf)
                        frame_items = self._extract_items_from_outfit(outfit, frame_index=frame_index)
                        frame_results.append(frame_items)

                    all_detected_items = [
                        item
                        for frame_items in frame_results
                        for item in frame_items
                    ]

                    decision_status, relevance_score, reason, metrics = self.classify_fashion_relevance(
                        video=video,
                        frame_results=frame_results,
                        frame_count=len(frame_paths)
                    )

                    # Luôn lưu AIAnalysis để sau này giải thích vì sao video được nhận/loại.
                    self._save_ai_analysis(
                        video_id=video.video_id,
                        decision_status=decision_status,
                        relevance_score=relevance_score,
                        reason=reason,
                        metrics=metrics,
                        detected_items=all_detected_items
                    )

                    # Chỉ video đủ điều kiện thời trang mới được lưu FashionItem và đưa vào trend_history.
                    if decision_status == 'success':
                        for item_data in all_detected_items:
                            new_item = FashionItem(
                                video_id=video.video_id,
                                item_type=item_data['item_type'],
                                confidence=item_data['confidence'],
                                bbox=item_data['bbox'],
                                detected_at=datetime.now()
                            )
                            self.db.add(new_item)

                        video.processing_status = 'success'
                    else:
                        # uncertain/failed_no_fashion đều không được build trend_history vì builder chỉ lấy success.
                        video.processing_status = decision_status

                    video.is_analyzed = True
                    self.db.commit()
                    total_processed += 1

                    logger.info(
                        f"   ✅ Xong: Status={video.processing_status}, "
                        f"score={relevance_score:.1f}, reason={reason}"
                    )

                except Exception as e:
                    # Sau lỗi flush/commit, SQLAlchemy Session bắt buộc rollback trước.
                    # Không đọc video.video_id trực tiếp trong trạng thái PendingRollback.
                    self.db.rollback()
                    logger.error(f"   ❌ Lỗi nghiêm trọng tại video {current_video_id}: {e}")

                    # Đánh dấu error để không bị lặp lại vô tận và dễ phân biệt lỗi kỹ thuật.
                    try:
                        video = self.db.query(Video).filter(Video.video_id == current_video_id).first()
                        if video:
                            video.processing_status = 'error'
                            video.is_analyzed = True
                            self._save_ai_analysis(
                                video_id=current_video_id,
                                decision_status='error',
                                relevance_score=0.0,
                                reason=str(e)[:500],
                                metrics={},
                                detected_items=[]
                            )
                            self.db.commit()
                    except Exception as inner_e:
                        self.db.rollback()
                        logger.error(f"   ❌ Không thể đánh dấu error cho video {current_video_id}: {inner_e}")
                finally:
                    for f_path in frame_paths:
                        if os.path.exists(f_path):
                            try:
                                os.remove(f_path)
                            except Exception:
                                pass

        return {
            "status": "completed",
            "processed_count": total_processed,
            "message": "YOLO + fashion relevance filtering completed."
        }


if __name__ == "__main__":
    processor = FashionBatchProcessor(model_path='ai/models/yolov8m_fashion_best.pt')

    logger.info("🚀 BẮT ĐẦU QUY TRÌNH QUÉT TOÀN BỘ CƠ SỞ DỮ LIỆU...")
    result = processor.process_all_videos(batch_size=20)
    logger.info(f"🏁 Kết quả: {result}")