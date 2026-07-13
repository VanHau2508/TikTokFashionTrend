import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from typing import Callable

from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from database.config import SessionLocal
from database.models import Video

load_dotenv()

logger = logging.getLogger(__name__)


class VideoCoverUrlUpdater:
    """
    Cập nhật videos.cover_url từ video_url TikTok.

    Dùng cho admin:
    - Chỉ cập nhật video thiếu cover_url hoặc cover_url không hợp lệ.
    - Có thể chạy theo danh sách video_ids được chọn.
    - Có thể giới hạn theo is_in_scope.
    """

    def __init__(self, cookies_file: str = "cookies.json"):
        self.db = SessionLocal()
        self.cookies_file = cookies_file

    def load_cookies(self):
        try:
            with open(self.cookies_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            logger.info("✅ Loaded %s cookies", len(cookies))
            return cookies
        except FileNotFoundError:
            logger.warning("⚠️ Không tìm thấy %s. Vẫn chạy nhưng dễ bị TikTok chặn.", self.cookies_file)
            return []
        except Exception as exc:
            logger.warning("⚠️ Lỗi load cookies: %s", exc)
            return []

    @staticmethod
    def _invalid_cover_filter():
        return (
            (Video.cover_url == None)
            | (Video.cover_url == "")
            | (Video.cover_url == Video.video_url)
            | (Video.cover_url.like("%/video/%"))
            | (Video.cover_url.like("https://www.tiktok.com/%"))
        )

    def get_videos_need_update(
        self,
        limit: int = 100,
        scope: str = "in_scope",
        video_ids: list[int] | None = None,
    ):
        query = self.db.query(Video).filter(
            Video.video_url.isnot(None),
            Video.video_url != "",
            self._invalid_cover_filter(),
        )

        if video_ids:
            query = query.filter(Video.video_id.in_(video_ids))
        else:
            if scope == "in_scope":
                query = query.filter(Video.is_in_scope == True)
            elif scope == "out_scope":
                query = query.filter(Video.is_in_scope == False)

        return (
            query.order_by(Video.video_id.desc())
            .limit(limit)
            .all()
        )

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

    async def update_single_video(self, context, video: Video):
        page = await context.new_page()

        try:
            logger.info("🔍 Video ID %s | TikTok ID %s", video.video_id, video.tiktok_video_id)

            await page.goto(
                video.video_url,
                wait_until="domcontentloaded",
                timeout=50000,
            )

            await page.wait_for_timeout(random.randint(1800, 3200))

            content = await page.content()
            content_lower = content.lower()

            if "access denied" in content_lower or "you don't have permission" in content_lower:
                logger.warning("🚫 Access denied: %s", video.video_url)
                return False

            cover_url = await self.extract_cover_url_from_page(page)

            if not cover_url and ("captcha" in content_lower or "slider" in content_lower):
                logger.warning("⚠️ CAPTCHA/chặn dữ liệu tại: %s", video.video_url)

                # Trong chế độ headless=False, admin có thể tự giải captcha trên trình duyệt.
                # Trong headless=True, vòng này vẫn chờ một chút để TikTok hydrate JSON nếu có.
                for _ in range(8):
                    await asyncio.sleep(3)
                    cover_url = await self.extract_cover_url_from_page(page)
                    if cover_url:
                        break

            if not cover_url:
                logger.warning("⚠️ Không lấy được cover_url cho video_id=%s", video.video_id)
                return False

            if "/video/" in cover_url and "tiktok.com" in cover_url:
                logger.warning("⚠️ cover_url không hợp lệ, vẫn là video_url: %s", cover_url)
                return False

            video.cover_url = cover_url

            if hasattr(video, "updated_at"):
                video.updated_at = datetime.now(timezone.utc)

            self.db.commit()

            logger.info("✅ Updated cover_url video_id=%s", video.video_id)
            return True

        except PlaywrightTimeoutError:
            self.db.rollback()
            logger.warning("⏱️ Timeout video_id=%s", video.video_id)
            return False

        except Exception as exc:
            self.db.rollback()
            logger.error("❌ Lỗi video_id=%s: %s", video.video_id, exc)
            return False

        finally:
            await page.close()

    async def run(
        self,
        limit: int = 100,
        concurrent_tabs: int = 2,
        headless: bool = True,
        scope: str = "in_scope",
        video_ids: list[int] | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ):
        videos = self.get_videos_need_update(
            limit=limit,
            scope=scope,
            video_ids=video_ids,
        )

        total = len(videos)

        if not videos:
            result = {
                "total": 0,
                "success": 0,
                "failed": 0,
                "message": "Không có video nào cần cập nhật ảnh bìa.",
            }
            if progress_callback:
                progress_callback(result)
            return result

        cookies = self.load_cookies()

        logger.info("🚀 Bắt đầu cập nhật cover_url cho %s videos", total)

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
                except Exception as exc:
                    logger.warning("⚠️ Không inject được cookies: %s", exc)

            await context.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'vi', 'en-US', 'en'] });
                """
            )

            success_count = 0
            failed_count = 0
            processed_count = 0
            concurrent_tabs = max(1, min(int(concurrent_tabs or 1), 5))

            for i in range(0, total, concurrent_tabs):
                chunk = videos[i:i + concurrent_tabs]
                results = await asyncio.gather(
                    *[self.update_single_video(context, video) for video in chunk]
                )

                success_count += sum(1 for item in results if item)
                failed_count += sum(1 for item in results if not item)
                processed_count += len(chunk)

                progress = {
                    "total": total,
                    "processed": processed_count,
                    "success": success_count,
                    "failed": failed_count,
                }

                if progress_callback:
                    progress_callback(progress)

                logger.info(
                    "📊 Tiến độ: %s/%s | Success=%s | Failed=%s",
                    processed_count,
                    total,
                    success_count,
                    failed_count,
                )

                await asyncio.sleep(random.uniform(3, 7))

            await browser.close()

        return {
            "total": total,
            "processed": processed_count,
            "success": success_count,
            "failed": failed_count,
            "message": "Hoàn tất cập nhật ảnh bìa video.",
        }

    def close(self):
        self.db.close()
