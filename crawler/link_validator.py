"""
Video Link Validator - Kiểm tra link TikTok có 'sống' và 'truy cập được' trước khi lưu DB
- Loại bỏ video có giỏ hàng (app-only)
- Loại bỏ video bị xóa/đã chết
- Chỉ lưu link "sống" vào CSDL
"""

import subprocess
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

class VideoLinkValidator:
    """Kiểm tra xem link TikTok có hoạt động không"""
    
    # Các lỗi cần lọc bỏ
    BLOCKED_ERRORS = [
        'Video unavailable',          # Video đã bị xóa
        'This video is unavailable',  # Video không khả dụng
        'Sign in to continue',        # Yêu cầu đăng nhập
        'This video has been removed', # Video bị gỡ
        'Not Found',                  # 404 - Video không tồn tại
        'Forbidden',                  # 403 - Bị chặn (giỏ hàng)
        'This account',               # Tài khoản bị khóa
    ]
    
    @staticmethod
    def check_link_alive(tiktok_url: str, timeout: int = 15) -> Tuple[bool, Optional[str]]:
        """
        Kiểm tra link TikTok có 'sống' không bằng yt-dlp (chế độ Simulate)
        
        Args:
            tiktok_url: URL TikTok cần kiểm tra
            timeout: Timeout tối đa (giây)
        
        Returns:
            (True, direct_url):   Link OK, trả về URL trực tiếp
            (False, None):        Link chết/bị chặn, bỏ qua
        
        Example:
            is_alive, url = VideoLinkValidator.check_link_alive(
                'https://www.tiktok.com/@user/video/123456'
            )
            if is_alive:
                print(f"✅ Link live: {url}")
            else:
                print("❌ Link chết")
        """
        try:
            logger.debug(f"🔍 Kiểm tra link: {tiktok_url[:60]}...")
            
            # Lệnh yt-dlp chế độ Simulate (không tải video)
            cmd = [
                'yt-dlp',
                '--simulate',                    # Mô phỏng - không tải
                '--get-url',                     # Lấy URL trực tiếp
                '--quiet',                       # Không in log thừa
                '--no-warnings',
                '--socket-timeout', '10',
                '--user-agent', 
                'Mozilla/5.0 (iPhone; CPU iPhone OS 14_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
                tiktok_url
            ]
            
            # Chạy lệnh và đợi kết quả (tối đa 15 giây)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8'
            )
            
            # Kiểm tra kết quả
            output = result.stdout.strip()
            error = result.stderr.strip()
            
            # Nếu return code 0 và có URL trả về = link sống ✅
            if result.returncode == 0 and output:
                logger.info(f"✅ Link LIVE: {tiktok_url[:60]}...")
                return True, output
            
            # Kiểm tra lỗi cụ thể
            error_lower = error.lower()
            for blocked in VideoLinkValidator.BLOCKED_ERRORS:
                if blocked.lower() in error_lower:
                    reason = blocked
                    logger.warning(
                        f"❌ Link CHẾT: {tiktok_url[:60]}... "
                        f"(Lý do: {reason})"
                    )
                    return False, None
            
            # Nếu không có lỗi cụ thể nhưng thất bại
            logger.warning(
                f"❌ Link không truy cập được: {tiktok_url[:60]}... "
                f"(Lỗi: {error[:100] if error else 'Unknown'})"
            )
            return False, None
            
        except subprocess.TimeoutExpired:
            logger.warning(
                f"⏱️ TIMEOUT: Link quá chậm: {tiktok_url[:60]}... "
                f"(Có thể bị chặn)"
            )
            return False, None
            
        except Exception as e:
            logger.error(
                f"⚠️ Lỗi kiểm tra link: {tiktok_url[:60]}... "
                f"(Exception: {str(e)[:50]})"
            )
            return False, None
    
    @staticmethod
    def validate_video_data(video_data: dict) -> Tuple[bool, Optional[dict], str]:
        """
        Kiểm tra dữ liệu video hoàn chỉnh (URL liveness + data validation)
        
        Args:
            video_data: Dict chứa thông tin video
                {
                    'video_id': '123456',
                    'video_url': 'https://www.tiktok.com/...',
                    'description': '...',
                    'author': '...',
                    ...
                }
        
        Returns:
            (True, video_data, reason):   Dữ liệu hợp lệ ✅
            (False, None, reason):        Dữ liệu không hợp lệ ❌
        
        Example:
            is_valid, clean_data, msg = VideoLinkValidator.validate_video_data(raw_video)
            if is_valid:
                save_to_db(clean_data)
            else:
                print(f"Video lọc bỏ: {msg}")
        """
        # 1️⃣ Kiểm tra NULL/rỗng
        if not video_data:
            return False, None, "Video data rỗng"
        
        video_url = video_data.get('video_url', '').strip()
        video_id = video_data.get('video_id', '').strip()
        author = video_data.get('author', '').strip()
        
        # 2️⃣ Kiểm tra video_id hợp lệ
        if not video_id or not video_id.isdigit():
            return False, None, f"Video ID không hợp lệ: {video_id}"
        
        # 3️⃣ Kiểm tra URL hợp lệ
        if not video_url or 'tiktok.com' not in video_url.lower():
            return False, None, f"URL không hợp lệ: {video_url[:50]}"
        
        # 4️⃣ Kiểm tra author không rỗng
        if not author or len(author) < 1:
            return False, None, "Author trống"
        
        # 5️⃣ Kiểm tra link có 'sống' không (CÓ THỜI GIAN)
        is_alive, direct_url = VideoLinkValidator.check_link_alive(video_url)
        
        if not is_alive:
            return False, None, f"Link chết/bị chặn"
        
        # 6️⃣ Dữ liệu hợp lệ - trả về dữ liệu clean
        cleaned_data = {
            'video_id': video_id,
            'video_url': video_url,
            'direct_url': direct_url,  # 🆕 URL stream trực tiếp
            'description': video_data.get('description', '').strip(),
            'author': author,
            'views_text': video_data.get('views_text', 'N/A'),
            'likes_text': video_data.get('likes_text', 'N/A'),
        }
        
        return True, cleaned_data, "✅ Video hợp lệ"
    
    @staticmethod
    def batch_validate(video_list: list) -> Tuple[list, dict]:
        """
        Kiểm tra một batch videos (danh sách)
        
        Args:
            video_list: Danh sách dict videos
        
        Returns:
            (valid_videos, stats):
            - valid_videos: Danh sách videos đã qua kiểm tra
            - stats: Thống kê {total, valid, invalid, invalid_reasons}
        """
        valid_videos = []
        stats = {
            'total': len(video_list),
            'valid': 0,
            'invalid': 0,
            'invalid_reasons': {}  # Đếm lý do từng lỗi
        }
        
        logger.info(f"🔍 Kiểm tra {len(video_list)} videos...")
        
        for idx, video in enumerate(video_list, 1):
            is_valid, clean_data, reason = VideoLinkValidator.validate_video_data(video)
            
            if is_valid:
                valid_videos.append(clean_data)
                stats['valid'] += 1
                logger.info(f"   ✅ [{idx}/{len(video_list)}] OK")
            else:
                stats['invalid'] += 1
                # Đếm lý do lỗi
                if reason not in stats['invalid_reasons']:
                    stats['invalid_reasons'][reason] = 0
                stats['invalid_reasons'][reason] += 1
                logger.warning(f"   ❌ [{idx}/{len(video_list)}] {reason}")
        
        # In tóm tắt
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 Kết quả kiểm tra:")
        logger.info(f"   Tổng: {stats['total']} | ✅ Trung thực: {stats['valid']} | ❌ Lỗi: {stats['invalid']}")
        logger.info(f"   Pass rate: {(stats['valid']/stats['total']*100 if stats['total'] > 0 else 0):.1f}%")
        
        if stats['invalid_reasons']:
            logger.info(f"\n   Các lỗi gặp:")
            for reason, count in sorted(stats['invalid_reasons'].items(), key=lambda x: x[1], reverse=True):
                logger.info(f"      - {reason}: {count} videos")
        logger.info(f"{'='*60}\n")
        
        return valid_videos, stats
