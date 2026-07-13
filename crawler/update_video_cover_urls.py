import asyncio
import json
import logging
import random
from datetime import datetime, timezone

from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from database.config import SessionLocal
from database.models import Video

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoCoverUrlUpdater:
    """
    Cập nhật lại videos.cover_url từ video_url TikTok hiện có.
    """

    def __init__(self, cookies_file="cookies.json"):
        self.db = SessionLocal()
        self.cookies_file = cookies_file

    def load_cookies(self):
        try:
            with open(self.cookies_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            logger.info(f"✅ Loaded {len(cookies)} cookies")
            return cookies
        except FileNotFoundError:
            logger.warning(f"⚠️ Không tìm thấy {self.cookies_file}. Vẫn chạy nhưng dễ bị TikTok chặn.")
            return []
        except Exception as e:
            logger.warning(f"⚠️ Lỗi load cookies: {e}")
            return []

    def get_videos_need_update(self, limit=20):
        videos = (
            self.db.query(Video)
            .filter(
                Video.video_url.isnot(None),
                Video.video_url != "",
            )
            .filter(
                (Video.cover_url == None)
                | (Video.cover_url == "")
                | (Video.cover_url == Video.video_url)
                | (Video.cover_url.like("%/video/%"))
                | (Video.cover_url.like("https://www.tiktok.com/%"))
            )
            .limit(limit)
            .all()
        )
        return videos

    async def extract_cover_url_from_page(self, page):
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

    async def update_single_video(self, context, video):
        page = await context.new_page()

        try:
            logger.info(f"🔍 Video ID {video.video_id} | TikTok ID {video.tiktok_video_id}")

            await page.goto(
                video.video_url,
                wait_until="domcontentloaded",
                timeout=50000
            )

            await page.wait_for_timeout(random.randint(2000, 3500))

            content = await page.content()
            content_lower = content.lower()

            if "access denied" in content_lower or "you don't have permission" in content_lower:
                logger.warning(f"🚫 Access denied: {video.video_url}")
                return False

            # 1. Thử lấy cover_url xem có được luôn không (nếu không dính captcha)
            cover_url = await self.extract_cover_url_from_page(page)

            # 2. Nếu CHƯA lấy được ảnh VÀ nghi ngờ có dấu hiệu CAPTCHA chặn dữ liệu
            if not cover_url and ("captcha" in content_lower or "slider" in content_lower):
                logger.warning(f"⚠️ PHÁT HIỆN CAPTCHA tại: {video.video_url}")
                logger.warning("⏳ HỆ THỐNG TẠM DỪNG! Bạn có 30 giây để kéo thả giải CAPTCHA trên màn hình trình duyệt...")
                
                captcha_solved = False
                # Vòng lặp kiểm tra mỗi 2 giây
                for step in range(20):
                    await asyncio.sleep(10)
                    try:
                        # ĐỔI LUẬT: Kiểm tra xem TRÍCH XUẤT ĐƯỢC ẢNH CHƯA thay vì tìm chữ captcha
                        cover_url = await self.extract_cover_url_from_page(page)
                        if cover_url:
                            captcha_solved = True
                            logger.info("🎉 Tuyệt vời! Đã trích xuất thành công dữ liệu ảnh sau khi giải CAPTCHA.")
                            break
                    except Exception:
                        break
                
                if not captcha_solved:
                    logger.error("❌ Đã quá 30 giây mà hệ thống vẫn không tìm thấy link ảnh cover. Bỏ qua video này.")
                    return False

            # 3. Kiểm tra lại một lần nữa để đảm bảo có dữ liệu
            if not cover_url:
                logger.warning(f"⚠️ Không lấy được cover_url cho video_id={video.video_id} (Dù trang đã tải xong)")
                return False

            if "/video/" in cover_url and "tiktok.com" in cover_url:
                logger.warning(f"⚠️ cover_url không hợp lệ, vẫn là video_url: {cover_url}")
                return False

            # Tiến hành lưu vào database
            video.cover_url = cover_url

            if hasattr(video, "updated_at"):
                video.updated_at = datetime.now(timezone.utc)

            self.db.commit()

            logger.info(f"✅ Updated cover_url video_id={video.video_id}")
            logger.info(f"   {cover_url[:120]}")

            return True

        except PlaywrightTimeoutError:
            self.db.rollback()
            logger.warning(f"⏱️ Timeout video_id={video.video_id}")
            return False

        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Lỗi video_id={video.video_id}: {e}")
            return False

        finally:
            await page.close()

    async def run(self, limit=300, concurrent_tabs=3, headless=False):
        videos = self.get_videos_need_update(limit=limit)

        if not videos:
            logger.info("✨ Không có video nào cần cập nhật cover_url.")
            return

        logger.info(f"🚀 Bắt đầu cập nhật cover_url cho {len(videos)} videos")
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

                # Khoảng nghỉ an toàn giữa các lượt mở tab
                await asyncio.sleep(random.uniform(5, 10))

            await browser.close()

        logger.info("=" * 70)
        logger.info("🏁 HOÀN TẤT CẬP NHẬT COVER_URL")
        logger.info(f"✅ Thành công: {success_count}")
        logger.info(f"❌ Thất bại: {failed_count}")
        logger.info("=" * 70)

    def close(self):
        self.db.close()


async def main():
    updater = VideoCoverUrlUpdater(cookies_file="cookies.json")
    try:
        # LƯU Ý: Để concurrent_tabs=1 để giải CAPTCHA thủ công từng tab một cách dễ dàng
        await updater.run(
            limit=300,
            concurrent_tabs=3, 
            headless=False
        )
    finally:
        updater.close()


if __name__ == "__main__":
    asyncio.run(main())