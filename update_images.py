import asyncio
import json
import logging
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from sqlalchemy import or_

from database.config import SessionLocal
from database.models import Video

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class VideoTask:
    video_id: int
    tiktok_video_id: str | None
    video_url: str


class VideoCoverLocalUpdater:
    """
    Cập nhật videos.cover_url theo hướng:
    TikTok video_url -> lấy cover_url -> tải ảnh về frontend/public/media/covers
    -> lưu vào DB dạng /media/covers/cover_xxx.jpg
    """

    def __init__(
        self,
        cookies_file="cookies.json",
        save_dir="frontend/public/media/covers",
        public_url_prefix="/media/covers",
    ):
        self.cookies_file = cookies_file

        # Thư mục vật lý để lưu ảnh
        self.save_dir = Path(save_dir)

        # Path public mà frontend Vite đọc được
        self.public_url_prefix = public_url_prefix.rstrip("/")

        # Tự động tạo frontend/public/media/covers nếu chưa có
        self.save_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"📁 Ảnh sẽ được lưu tại: {self.save_dir.resolve()}")
        logger.info(f"🌐 DB sẽ lưu cover_url dạng: {self.public_url_prefix}/cover_xxx.jpg")

    def load_cookies(self):
        try:
            with open(self.cookies_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)

            logger.info(f"✅ Loaded {len(cookies)} cookies")
            return cookies

        except FileNotFoundError:
            logger.warning(
                f"⚠️ Không tìm thấy {self.cookies_file}. "
                "Vẫn chạy nhưng dễ bị TikTok chặn/captcha."
            )
            return []

        except Exception as e:
            logger.warning(f"⚠️ Lỗi load cookies: {e}")
            return []

    def get_videos_need_update(self, limit=600):
        """
        Chỉ lấy dữ liệu cần thiết, không truyền ORM object qua nhiều async task.
        Điều này ổn định hơn khi chạy concurrent.
        """
        db = SessionLocal()

        try:
            rows = (
                db.query(
                    Video.video_id,
                    Video.tiktok_video_id,
                    Video.video_url,
                )
                .filter(
                    Video.video_url.isnot(None),
                    Video.video_url != "",
                )
                .filter(
                    or_(
                        Video.cover_url == None,
                        Video.cover_url == "",
                        Video.cover_url == Video.video_url,
                        Video.cover_url.like("%/video/%"),
                        Video.cover_url.like("https://www.tiktok.com/%"),
                        Video.cover_url.like("https://vt.tiktok.com/%"),
                        Video.cover_url.like("https://vm.tiktok.com/%"),

                        # Quan trọng:
                        # Những link ảnh online cũ như tiktokcdn/http sẽ được tải lại về local.
                        Video.cover_url.like("http%"),
                    )
                )
                .limit(limit)
                .all()
            )

            return [
                VideoTask(
                    video_id=row.video_id,
                    tiktok_video_id=row.tiktok_video_id,
                    video_url=row.video_url,
                )
                for row in rows
            ]

        finally:
            db.close()

    async def extract_cover_url_from_page(self, page):
        """
        Lấy cover_url từ dữ liệu TikTok trong page.
        Ưu tiên JSON nội bộ, sau đó fallback sang meta og:image/twitter:image.
        """
        cover_url = await page.evaluate(
            """
            () => {
                function pickCoverFromItem(item) {
                    if (!item) return null;

                    const video = item.video || {};

                    const covers = [
                        video.cover,
                        video.originCover,
                        video.dynamicCover,
                        video.animatedCover,
                        item.cover,
                        item.imagePost?.cover?.imageURL?.urlList?.[0],
                    ];

                    for (const url of covers) {
                        if (url && typeof url === 'string' && url.startsWith('http')) {
                            return url;
                        }
                    }

                    return null;
                }

                try {
                    const universal = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');

                    if (universal) {
                        const data = JSON.parse(universal.textContent);

                        const item =
                            data.__DEFAULT_SCOPE__?.['webapp.video-detail']?.itemInfo?.itemStruct ||
                            data.__DEFAULT_SCOPE__?.['webapp.video-detail']?.itemInfo?.itemStructV2;

                        const cover = pickCoverFromItem(item);
                        if (cover) return cover;
                    }
                } catch (e) {}

                try {
                    const sigi = document.getElementById('SIGI_STATE');

                    if (sigi) {
                        const data = JSON.parse(sigi.textContent);
                        const itemModule = data.ItemModule || {};
                        const firstKey = Object.keys(itemModule)[0];
                        const item = itemModule[firstKey];

                        const cover = pickCoverFromItem(item);
                        if (cover) return cover;
                    }
                } catch (e) {}

                const metaSelectors = [
                    'meta[property="og:image"]',
                    'meta[name="twitter:image"]',
                    'meta[property="twitter:image"]'
                ];

                for (const selector of metaSelectors) {
                    const meta = document.querySelector(selector);
                    const content = meta?.getAttribute('content');

                    if (content && content.startsWith('http')) {
                        return content;
                    }
                }

                const img = document.querySelector('img[src*="tiktokcdn"], img[src*="tiktok"]');

                if (img?.src && img.src.startsWith('http')) {
                    return img.src;
                }

                return null;
            }
            """
        )

        return cover_url

    def make_safe_filename(self, video: VideoTask, ext: str):
        raw_id = video.tiktok_video_id or str(video.video_id)

        # Chỉ giữ ký tự an toàn cho tên file
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(raw_id))

        return f"cover_{safe_id}.{ext}"

    def get_image_extension(self, content_type: str):
        content_type = content_type.lower()

        if "png" in content_type:
            return "png"

        if "webp" in content_type:
            return "webp"

        if "gif" in content_type:
            return "gif"

        return "jpg"

    async def download_cover_to_local(self, context, video: VideoTask, cover_url: str):
        """
        Tải ảnh về frontend/public/media/covers.
        Trả về public path để lưu DB, ví dụ /media/covers/cover_xxx.jpg
        """
        image_response = await context.request.get(
            cover_url,
            timeout=30000,
            headers={
                "Referer": "https://www.tiktok.com/",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
            },
        )

        if not image_response.ok:
            logger.warning(
                f"⚠️ Không thể tải ảnh. "
                f"Status={image_response.status} | URL={cover_url}"
            )
            return None

        content_type = image_response.headers.get("content-type", "").lower()

        if not content_type.startswith("image/"):
            logger.warning(
                f"⚠️ URL không trả về ảnh thật. "
                f"Content-Type={content_type} | URL={cover_url}"
            )
            return None

        image_data = await image_response.body()

        if not image_data or len(image_data) < 1024:
            logger.warning(f"⚠️ File ảnh quá nhỏ hoặc rỗng, bỏ qua: {cover_url}")
            return None

        ext = self.get_image_extension(content_type)
        filename = self.make_safe_filename(video, ext)

        final_path = self.save_dir / filename
        temp_path = self.save_dir / f"{filename}.tmp"

        # Ghi file tạm trước, sau đó replace để tránh file bị ghi dở
        with open(temp_path, "wb") as f:
            f.write(image_data)

        os.replace(temp_path, final_path)

        public_path = f"{self.public_url_prefix}/{filename}"

        return public_path

    def update_video_cover_in_db(self, video_id: int, public_path: str):
        """
        Mỗi video dùng session riêng để tránh lỗi khi chạy nhiều task async.
        """
        db = SessionLocal()

        try:
            video = db.query(Video).filter(Video.video_id == video_id).first()

            if not video:
                logger.warning(f"⚠️ Không tìm thấy video_id={video_id} trong DB")
                return False

            video.cover_url = public_path

            if hasattr(video, "updated_at"):
                video.updated_at = datetime.now(timezone.utc)

            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Lỗi cập nhật DB video_id={video_id}: {e}")
            return False

        finally:
            db.close()

    async def update_single_video(self, context, video: VideoTask):
        page = await context.new_page()

        try:
            logger.info(f"🔍 Video ID {video.video_id} | TikTok ID {video.tiktok_video_id}")

            await page.goto(
                video.video_url,
                wait_until="domcontentloaded",
                timeout=50000,
            )

            await page.wait_for_timeout(random.randint(2000, 3500))

            content = await page.content()
            content_lower = content.lower()

            if "access denied" in content_lower or "you don't have permission" in content_lower:
                logger.warning(f"🚫 Access denied: {video.video_url}")
                return False

            cover_url = await self.extract_cover_url_from_page(page)

            if not cover_url and ("captcha" in content_lower or "slider" in content_lower):
                logger.warning(f"⚠️ PHÁT HIỆN CAPTCHA tại: {video.video_url}")
                logger.warning("⏳ Bạn có khoảng 30 giây để giải CAPTCHA trên trình duyệt...")

                captcha_solved = False

                for _ in range(20):
                    await asyncio.sleep(1.5)

                    cover_url = await self.extract_cover_url_from_page(page)

                    if cover_url:
                        captcha_solved = True
                        logger.info("🎉 Đã lấy được cover_url sau khi giải CAPTCHA.")
                        break

                if not captcha_solved:
                    logger.error("❌ Không lấy được cover_url sau CAPTCHA. Bỏ qua video này.")
                    return False

            if not cover_url:
                logger.warning(f"⚠️ Không lấy được cover_url cho video_id={video.video_id}")
                return False

            if "/video/" in cover_url and "tiktok.com" in cover_url:
                logger.warning(f"⚠️ cover_url không hợp lệ, vẫn là video_url: {cover_url}")
                return False

            public_path = await self.download_cover_to_local(context, video, cover_url)

            if not public_path:
                return False

            updated = self.update_video_cover_in_db(video.video_id, public_path)

            if not updated:
                return False

            logger.info(f"✅ Updated video_id={video.video_id} -> {public_path}")
            return True

        except PlaywrightTimeoutError:
            logger.warning(f"⏱️ Timeout video_id={video.video_id}")
            return False

        except Exception as e:
            logger.error(f"❌ Lỗi video_id={video.video_id}: {e}")
            return False

        finally:
            await page.close()

    async def run(self, limit=600, concurrent_tabs=2, headless=False):
        videos = self.get_videos_need_update(limit=limit)

        if not videos:
            logger.info("✨ Không có video nào cần cập nhật/tải ảnh.")
            return

        logger.info(f"🚀 Bắt đầu tải cover cho {len(videos)} videos")
        logger.info(f"⚙️ concurrent_tabs={concurrent_tabs}")

        cookies = self.load_cookies()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )

            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                locale="vi-VN",
                timezone_id="Asia/Ho_Chi_Minh",
            )

            if cookies:
                try:
                    await context.add_cookies(cookies)
                    logger.info("🍪 Cookies injected")
                except Exception as e:
                    logger.warning(f"⚠️ Không inject được cookies: {e}")

            await context.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'vi', 'en-US', 'en'] });
                """
            )

            success_count = 0
            failed_count = 0

            for i in range(0, len(videos), concurrent_tabs):
                chunk = videos[i:i + concurrent_tabs]

                tasks = [
                    self.update_single_video(context, video)
                    for video in chunk
                ]

                results = await asyncio.gather(*tasks)

                success_count += sum(1 for item in results if item)
                failed_count += sum(1 for item in results if not item)

                logger.info(
                    f"📊 Tiến độ: {min(i + concurrent_tabs, len(videos))}/{len(videos)} | "
                    f"Success={success_count} | Failed={failed_count}"
                )

                await asyncio.sleep(random.uniform(3, 7))

            await browser.close()

        logger.info("=" * 70)
        logger.info("🏁 HOÀN TẤT TẢI VÀ CẬP NHẬT COVER")
        logger.info(f"✅ Thành công: {success_count}")
        logger.info(f"❌ Thất bại: {failed_count}")
        logger.info("=" * 70)


async def main():
    updater = VideoCoverLocalUpdater(
        cookies_file="cookies.json",

        # Nếu bạn chạy script từ thư mục gốc project:
        save_dir="frontend/public/media/covers",

        # DB sẽ lưu dạng này để frontend Vite 5173 đọc được:
        public_url_prefix="/media/covers",
    )

    await updater.run(
        limit=600,

        # Ổn định nhất là 1.
        # Khi chạy ổn rồi có thể thử 2 hoặc 3.
        concurrent_tabs=2,

        # False để nếu gặp CAPTCHA còn giải tay được.
        headless=False,
    )


if __name__ == "__main__":
    asyncio.run(main())