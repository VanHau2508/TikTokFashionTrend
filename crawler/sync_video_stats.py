import asyncio
import logging
import re
import random
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright
from database.config import SessionLocal
from database.models import Video, VideoStat
from sqlalchemy import func
import argparse
from pathlib import Path
import os

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoStatsSyncer:
    def __init__(self):
        self.db = SessionLocal()
        
        self.tiktok_profile_dir = Path("browser_profiles/tiktok_stats_sync")
        self.tiktok_profile_dir.mkdir(parents=True, exist_ok=True)

    async def _sync_single_video(self, context, video, should_stop=None):
        """Xử lý từng video và cho phép dừng mềm bằng should_stop()."""

        def stop_requested():
            return should_stop is not None and should_stop()

        if stop_requested():
            logger.warning(f"🛑 Bỏ qua video {video.video_id} vì admin đã yêu cầu dừng task.")
            return "cancelled"

        page = await context.new_page()

        try:
            if stop_requested():
                return "cancelled"

            # TĂNG TỐC: Chặn các tài nguyên không cần thiết (Ảnh, video, fonts)
            await page.route(
                "**/*.{png,jpg,jpeg,gif,webp,svg,woff,ttf}",
                lambda route: route.abort()
            )

            logger.info(f"🔍 Đang quét: {video.tiktok_video_id}")

            if stop_requested():
                return "cancelled"

            # Điều hướng nhanh: Chỉ chờ đến khi bắt đầu load (commit)
            await page.goto(video.video_url, wait_until="commit", timeout=60000)

            if stop_requested():
                return "cancelled"

            # Đợi đúng thẻ chứa dữ liệu xuất hiện rồi bóc ngay
            try:
                await page.wait_for_selector("#__UNIVERSAL_DATA_FOR_REHYDRATION__", timeout=20000)
            except Exception:
                pass

            if stop_requested():
                return "cancelled"

            stats = await page.evaluate("""() => {
                try {
                    const el = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__') ||
                               document.getElementById('SIGI_STATE');
                    if (!el) return null;
                    const data = JSON.parse(el.textContent);
                    const item = data.__DEFAULT_SCOPE__?.['webapp.video-detail']?.itemInfo?.itemStruct ||
                                 data.ItemModule?.[Object.keys(data.ItemModule)[0]];
                    return item ? {
                        views: item.stats.playCount,
                        likes: item.stats.diggCount,
                        comments: item.stats.commentCount,
                        shares: item.stats.shareCount
                    } : null;
                } catch (e) { return null; }
            }""")

            if stop_requested():
                return "cancelled"

            if stats:
                # LUÔN THÊM MỚI (Để training LSTM)
                new_stat = VideoStat(
                    video_id=video.video_id,
                    view_count=int(stats.get('views') or 0),
                    like_count=self._parse_val(stats.get('likes')),
                    comment_count=self._parse_val(stats.get('comments')),
                    share_count=self._parse_val(stats.get('shares')),
                    collected_at=datetime.now(timezone.utc)
                )
                self.db.add(new_stat)
                self.db.commit()
                logger.info(f"✅ Đã lưu record mới cho ID {video.video_id}")
                return "success"

            logger.warning(f"⚠️ Không bóc được dữ liệu cho {video.tiktok_video_id}")
            return "no_data"

        except Exception as e:
            logger.error(f"❌ Lỗi video {video.video_id}: {str(e)[:160]}")
            self.db.rollback()
            return e

        finally:
            try:
                await page.close()
            except Exception:
                pass

    async def sync_all_stats(self, hours_gap=16, limit=2500, should_stop=None):
        """Lấy video chưa quét hoặc đã quét cách đây hơn hours_gap tiếng."""

        def stop_requested():
            return should_stop is not None and should_stop()

        time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours_gap)

        last_stat_subquery = self.db.query(
            VideoStat.video_id,
            func.max(VideoStat.collected_at).label("latest_date")
        ).group_by(VideoStat.video_id).subquery()

        # Chỉ đồng bộ chỉ số cho video đã được AI xác nhận là video thời trang.
        # Các video failed_no_frame / failed_no_fashion / uncertain / error không đi vào trend_history,
        # nên không cần tốn tài nguyên sync stats cho chúng.
        videos = self.db.query(Video).outerjoin(
            last_stat_subquery, Video.video_id == last_stat_subquery.c.video_id
        ).filter(
            Video.is_in_scope == True,
            Video.processing_status == "success",
            Video.is_analyzed == True,
            (last_stat_subquery.c.latest_date == None) |
            (last_stat_subquery.c.latest_date <= time_threshold)
        ).limit(limit).all()

        if not videos:
            logger.info(f"✨ Không có video nào cần cập nhật (Chu kỳ {hours_gap}h)")
            return {
                "status": "completed",
                "message": "Không có video nào cần cập nhật.",
                "processed": 0,
                "success": 0,
                "failed": 0,
                "cancelled": 0,
            }

        logger.info(f"🚀 Bắt đầu cập nhật {len(videos)} videos đã AI xác nhận là thời trang...")

        if stop_requested():
            logger.warning("🛑 Sync video stats đã bị dừng trước khi khởi chạy browser.")
            return {
                "status": "cancelled",
                "message": "Task đã được dừng bởi admin.",
                "processed": 0,
                "success": 0,
                "failed": 0,
                "cancelled": 0,
            }

        context = None
        processed = 0
        success_count = 0
        failed_count = 0
        cancelled_count = 0

        try:
            async with async_playwright() as p:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(self.tiktok_profile_dir),
                    headless=False,
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 720},
                    locale="vi-VN",
                    timezone_id="Asia/Ho_Chi_Minh",
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                    ],
                )

                CONCURRENT_TABS = 3

                for i in range(0, len(videos), CONCURRENT_TABS):
                    if stop_requested():
                        logger.warning("🛑 Admin đã yêu cầu dừng Sync Video Stats.")
                        return {
                            "status": "cancelled",
                            "message": "Task đã được dừng bởi admin.",
                            "processed": processed,
                            "success": success_count,
                            "failed": failed_count,
                            "cancelled": cancelled_count,
                        }

                    chunk = videos[i:i + CONCURRENT_TABS]

                    tasks = [
                        self._sync_single_video(context, video, should_stop=should_stop)
                        for video in chunk
                    ]

                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for result in results:
                        if result == "cancelled":
                            cancelled_count += 1
                        elif result == "success":
                            success_count += 1
                            processed += 1
                        elif result == "no_data":
                            failed_count += 1
                            processed += 1
                        elif isinstance(result, Exception):
                            failed_count += 1
                            logger.error(f"⚠️ Lỗi khi sync một video: {result}")
                        else:
                            processed += 1

                    if stop_requested():
                        logger.warning("🛑 Admin đã yêu cầu dừng sau khi xử lý chunk hiện tại.")
                        return {
                            "status": "cancelled",
                            "message": "Task đã được dừng bởi admin.",
                            "processed": processed,
                            "success": success_count,
                            "failed": failed_count,
                            "cancelled": cancelled_count,
                        }

                    await asyncio.sleep(random.uniform(4, 6))

                return {
                    "status": "completed",
                    "message": "Sync video stats hoàn tất.",
                    "processed": processed,
                    "success": success_count,
                    "failed": failed_count,
                    "cancelled": cancelled_count,
                }

        finally:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass

    def _parse_val(self, val):
        if isinstance(val, int): return val
        if not val: return 0
        text = str(val).upper().replace(',', '')
        multiplier = 1000 if 'K' in text else 1000000 if 'M' in text else 1
        match = re.search(r"(\d+\.?\d*)", text)
        return int(float(match.group(1)) * multiplier) if match else 0
    
async def main():

    parser = argparse.ArgumentParser(description="Run TikTok video stats syncer")

    parser.add_argument(
        "--hours-gap",
        type=int,
        default=16,
        help="Only sync videos whose latest stat is older than this number of hours"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=2500,
        help="Maximum number of videos to sync"
    )

    args = parser.parse_args()

    syncer = VideoStatsSyncer()

    try:
        await syncer.sync_all_stats(
            hours_gap=args.hours_gap,
            limit=args.limit
        )
    finally:
        try:
            syncer.db.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())