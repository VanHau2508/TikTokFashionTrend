from playwright.async_api import async_playwright
import asyncio
import logging
import json
from datetime import datetime, timezone
from database.config import SessionLocal
from crawler.base_crawler import BaseCrawler
from crawler.link_validator import VideoLinkValidator  # 🆕 Import Validator
from dotenv import load_dotenv
import random
import re
import os

from database.models import VideoStat, Video

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HashtagCrawlerWithCookies(BaseCrawler):
    """Crawl with authenticated cookies - bypass CAPTCHA!"""
    
    def __init__(self, cookies_file='cookies.json'):
        db = SessionLocal()
        super().__init__(db)
        self.cookies_file = cookies_file
        self.results = []
        self.logger = logging.getLogger(__name__)
    
    def load_cookies(self):
        """Load cookies from file"""
        try:
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            logger.info(f"✅ Loaded {len(cookies)} cookies")
            return cookies
        except FileNotFoundError:
            logger.error(f"❌ File not found: {self.cookies_file}")
            logger.info("💡 Please create cookies.json with your TikTok session cookies")
            return []
        except Exception as e:
            logger.error(f"❌ Error loading cookies: {e}")
            return []
        
    def _parse_number(self, text):
        if not text or text == '0' or text == 'N/A': 
            return 0
        # Chuyển về viết hoa, xóa dấu phẩy và các chữ tiếng Việt như 'lượt xem'
        text = str(text).strip().upper().replace(',', '')

        if not any(char.isdigit() for char in text):
            return 0
        
        multiplier = 1
        if 'K' in text: multiplier = 1000
        elif 'M' in text: multiplier = 1000000
        elif 'B' in text: multiplier = 1000000000
        
        # Chỉ trích xuất phần số (ví dụ: "14.5M lượt xem" -> "14.5")
        match = re.search(r"(\d+\.?\d*)", text)
        if match:
            try:
                return int(float(match.group(1)) * multiplier)
            except:
                return 0
        return 0
    
    def get_user_id_by_name(self, author_name):
        """Tìm ID người dùng theo username, nếu chưa có thì tạo mới."""
        from database.models import TikTokUser # Đảm bảo đã import model User
        
        # 1. Tìm xem user đã tồn tại chưa
        user = self.db.query(TikTokUser).filter(TikTokUser.nickname == author_name).first()
        
        if user:
            return user.tiktok_user_id
        
        # 2. Nếu chưa có, tạo một bản ghi User cơ bản
        new_user = TikTokUser(
            nickname=author_name,
            full_name=author_name, # Tạm thời để trùng tên
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user) # Để lấy được ID vừa tự sinh
        
        return new_user.tiktok_user_id
    
    def process_and_save(self, results):
        """Xử lý danh sách kết quả từ crawl_hashtag và CHỈ lưu vào bảng Video."""
        if not results:
            logger.warning("⚠️ Không có dữ liệu để lưu.")
            return

        saved_count = 0
        for video in results:
            try:
                # 1. Xử lý User (Tác giả)
                author_name = video.get('author', 'unknown_user')
                user_id = self.get_user_id_by_name(author_name)
                
                # 2. Lưu/Cập nhật thông tin video cơ bản vào bảng Video
                # Hàm upsert_video nên được viết để chỉ tác động lên bảng Video
                db_video_id = self.upsert_video(video, user_id) 
                
                if not db_video_id:
                    logger.warning(f"⚠️ Bỏ qua video do không lấy được ID: {video.get('video_id')}")
                    continue

                self.db.commit() # Lưu thông tin video
                saved_count += 1
                
            except Exception as e:
                self.db.rollback()
                logger.error(f"❌ Lỗi khi lưu video {video.get('video_id', 'unknown')}: {str(e)}")
                continue 
                    
        logger.info(f"💾 Hoàn tất! Đã lưu/cập nhật {saved_count} video gốc.")

    def _extract_hashtags(self, text):
        """Extract hashtags from text"""
        if not text:
            return []
        import re
        hashtags = re.findall(r'#\w+', text)
        return list(set(hashtags))    
    async def crawl_hashtag(self, hashtag, max_videos=300, max_scrolls=30, should_stop=None):
        """Crawl with cookies - FIX: Lấy description đúng"""

        def stop_requested():
            return should_stop is not None and should_stop()

        logger.info(f"\n{'='*70}")
        logger.info(f"🎯 Crawling: #{hashtag} (with authentication)")
        logger.info(f"{'='*70}")
        
        if stop_requested():
            logger.warning("🛑 Crawler đã bị dừng trước khi tạo job.")
            return []

        # Create job
        job_id = self.create_crawler_job(
            job_name=f"Crawl hashtag (auth): #{hashtag}",
            job_type='hashtag_auth',
            parameters={'hashtag': hashtag, 'max_videos': max_videos}
        )
        
        # Load cookies
        cookies = self.load_cookies()
        if not cookies:
            logger.warning("⚠️  No cookies loaded - may hit CAPTCHA")

        async with async_playwright() as p:
            try:
                logger.info("🌐 Launching browser...")
                browser = await p.chromium.launch(
                    headless=False,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                    ]
                )
                
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='vi-VN',
                    timezone_id='Asia/Ho_Chi_Minh'
                )
                
                # Add cookies
                if cookies:
                    try:
                        await context.add_cookies(cookies)
                        logger.info("🍪 Cookies injected!")
                    except Exception as e:
                        logger.warning(f"⚠️  Could not inject all cookies: {e}")
                
                # Hide webdriver
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['vi-VN', 'vi', 'en-US', 'en'],
                    });
                """)
                
                page = await context.new_page()
                
                # Navigate
                url = f"https://www.tiktok.com/tag/{hashtag}"
                logger.info(f"🔗 URL: {url}")
                
                response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                logger.info(f"✅ Status: {response.status}")
                
                await asyncio.sleep(3)
                
                # Check for CAPTCHA
                page_content = await page.content()
                
                if 'captcha' in page_content.lower() or 'slider' in page_content.lower():
                    logger.warning("⚠️  CAPTCHA/Slider detected!")
                    logger.info("📌 MANUAL ACTION REQUIRED:")
                    logger.info("   1. Look at the browser window")
                    logger.info("   2. Solve the CAPTCHA (rotate image, etc.)")
                    logger.info("   3. Wait for page to load automatically")
                    logger.info("   ⏳ Waiting 15s for you to solve it...")
                    
                    await asyncio.sleep(15)
                    logger.info("✅ Continuing after CAPTCHA...")
                
                await asyncio.sleep(10)
                
                # Count videos
                video_count = await page.evaluate("""
                    () => {
                        const selectors = [
                            '[data-e2e="challenge-item"]',
                            '[data-e2e="search-card-item"]',
                            'div[class*="DivItemContainer"]',
                        ];
                        
                        for (const selector of selectors) {
                            const elements = document.querySelectorAll(selector);
                            if (elements.length > 0) return elements.length;
                        }
                        return 0;
                    }
                """)
                
                logger.info(f"📊 Videos on page: {video_count}")
                
                if video_count == 0 and len(page_content) < 5000:
                    logger.warning("⚠️  Still blocked or empty page!")
                    self.update_crawler_job(job_id, 'failed', error_message='Page still empty after CAPTCHA')
                    await browser.close()
                    return []
                
                # Scroll
                logger.info(f"📜 Scrolling to load videos...")
                for i in range(max_scrolls):
                    if stop_requested():
                        logger.warning("🛑 Admin đã yêu cầu dừng crawler khi đang scroll.")
                        self.update_crawler_job(job_id, 'cancelled', error_message='Task đã được dừng bởi admin.')
                        return self.results

                    await page.evaluate("window.scrollBy(0, 800)")
                    await asyncio.sleep(2)
                    logger.info(f"   ⏬ Scroll {i+1}/{max_scrolls}")
                
                if stop_requested():
                    logger.warning("🛑 Admin đã yêu cầu dừng crawler trước khi extract dữ liệu.")
                    self.update_crawler_job(job_id, 'cancelled', error_message='Task đã được dừng bởi admin.')
                    return self.results

                # ✅ FIX: Extract videos dengan logic cải thiện
                logger.info(f"📦 Extracting video data...")

                videos = await page.evaluate(r"""
                    () => {
                        const results = [];
                        const blacklist = [
                            'giỏ hàng', 'mua tại', 'link bio', 'sale', 'voucher', 'freeship',
                            'đặt hàng', 'shop', 'cửa hàng', 'giá rẻ', 'ưu đãi', 'chốt đơn',
                            'full size', 'bảng size', 'kiểm hàng', 'thanh toán', 'cod',
                            'săn sale', 'giảm giá', 'mã giảm', 'hàng sẵn', 'tặng kèm',
                            'quà tặng', 'đơn hàng', 'hết hàng', 'còn hàng', 'vận chuyển',
                            'phí ship', 'đặt tại', 'nhấn vào đây', 'mua ngay', 'shopping'
                        ];

                        try {
                            // 1. Lấy túi dữ liệu ẩn (Metadata) - Nếu cần dùng sau này
                            const scriptTag = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
                            // Lưu ý: Đoạn này bạn đang để dở dang, tôi sẽ bọc nó lại để không gây lỗi
                            if (scriptTag) {
                                try {
                                    const rawData = JSON.parse(scriptTag.textContent);
                                    // Xử lý rawData nếu cần...
                                } catch (e) { console.error('Metadata parse error'); }
                            }

                            // 2. Quét các phần tử video trên giao diện (DOM)
                            const items = document.querySelectorAll('div[class*="DivItemContainer"]');
                            
                            items.forEach((elem) => {
                                try {
                                    // 1. Lấy video link
                                    const linkElem = elem.querySelector('a[href*="/video/"]');
                                    if (!linkElem) return;
                                    
                                    const videoUrl = linkElem.href;
                                    const videoId = videoUrl.match(/video\/(\d+)/)?.[1] || '';
                                    if (!videoId) return;
                                    
                                    // 2. Lấy Author
                                    let author = videoUrl.match(/@([^/]+)/)?.[1] || 'unknown';
                                    author = author.trim();
                                    
                                    // 3. Lấy Description
                                    let description = '';
                                    const titleAttr = linkElem.getAttribute('title') || '';
                                    const textDivs = elem.querySelectorAll('div[class*="DivDes"], span[class*="Text"], p, div[class*="Desc"]');
                                    
                                    for (let div of textDivs) {
                                        const text = div.innerText?.trim() || '';
                                        if (text && text !== author && !text.match(/^\d+$/) && text.length > 5) {
                                            description = text;
                                            break;
                                        }
                                    }
                                    
                                    if (!description) {
                                        description = titleAttr || `Video by ${author}`;
                                    }

                                    // 4. BỘ LỌC TỪ KHÓA (FILTER LOGIC)
                                    const descLower = description.toLowerCase();
                                    const isSpam = blacklist.some(word => descLower.includes(word));
                                    const hasShopAnchor = elem.querySelector('div[class*="AnchorShop"], div[class*="Shopping"], a[href*="shop"]');

                                    // 5. CHỈ PUSH KHI KHÔNG PHẢI SPAM/BÁN HÀNG
                                    if (!isSpam && !hasShopAnchor) {
                                        const vElem = elem.querySelector('[data-e2e="video-views"]') || 
                                                    elem.querySelector('strong[class*="video-count"]') ||
                                                    elem.querySelector('div[class*="StrongVideoCount"]') ||
                                                    elem.querySelector('strong');
                                            
                                        let viewsText = '0';
                                             
                                        results.push({
                                            video_id: videoId,
                                            video_url: videoUrl,
                                            description: description.trim().slice(0, 500),
                                            author: author,
                                            views_text: viewsText,
                                            likes_text: '0'
                                        });
                                    }
                                } catch (innerError) {
                                    console.error('Item parse error:', innerError);
                                }
                            });
                        } catch (outerError) {
                            console.error('Main evaluate error:', outerError);
                        }

                        return results;
                    }
                """)

                logger.info(f"✅ Extracted {len(videos)} videos!")

                # Show sample
                if videos:
                    logger.info(f"\n📋 Sample videos:")
                    for i in range(min(3, len(videos))):
                        logger.info(f"   [{i+1}] Author: {videos[i]['author']}")
                        logger.info(f"       Description: {videos[i]['description'][:60]}...")
                    logger.info("")
                
                # ✅ FIX: Validate using smart browser
                links_to_test = [v['video_url'] for v in videos[:5]]
                confirmed = await self.smart_browser_validator(context, links_to_test)
                
                if not confirmed:
                    logger.error("❌ Validation failed. Skipping batch.")
                    return []
                
                # Process videos
                videos_to_process = videos[:max_videos]
                videos_saved = 0
                
                for idx, video in enumerate(videos_to_process, 1):
                    if stop_requested():
                        logger.warning("🛑 Admin đã yêu cầu dừng crawler khi đang lưu video.")
                        self.update_crawler_job(job_id, 'cancelled', videos_collected=videos_saved)
                        return self.results

                    try:
                        if self.db.query(Video.video_id).filter(Video.tiktok_video_id == str(video['video_id'])).first():
                            logger.info(f"⏭️  [{idx}/{len(videos_to_process)}] Bỏ qua video đã tồn tại: {video['video_id']}")
                            continue

                        logger.info(f"📁 [{idx}/{len(videos_to_process)}] {video['author']} - {video['description'][:50]}...")
                        
                        # ✅ FIX: Save user correctly
                        tiktok_user_id = self.upsert_tiktok_user({
                            'unique_id': video['author'],
                            'nickname': video['author']
                        })
                        
                        if not tiktok_user_id:
                            logger.warning(f"   ⚠️  Could not save user {video['author']}")
                            continue
                        
                        # Save video
                        video_id = self.upsert_video({
                            'video_id': video['video_id'],
                            'description': video['description'],
                            'video_url': video['video_url'],
                            'cover_url': video['video_url']
                        }, tiktok_user_id)
                        
                        if not video_id:
                            logger.warning(f"   ⚠️  Could not save video {video['video_id']}")
                            continue
                        
                        # ✅ FIX: Extract & save hashtags WITH video_hashtags link
                        tags = self._extract_hashtags(video['description'])
                        
                        for tag in tags:
                            tag_name = tag.lstrip('#').lower()
                            
                            # Save hashtag
                            hashtag_id = self.upsert_hashtag(tag_name, 'general')
                            
                            if hashtag_id:
                                # ✅ NEW: Save video_hashtags link
                                self.link_video_hashtag(video_id, hashtag_id)
                                logger.debug(f"      → Linked #{tag_name}")
                        
                        videos_saved += 1
                    
                    except Exception as e:
                        logger.error(f"   ❌ Error: {e}")
                
                # Update job
                self.update_crawler_job(job_id, 'completed', videos_collected=videos_saved)
                
                logger.info(f"\n{'='*70}")
                logger.info(f"✅ Success: {videos_saved} videos saved")
                logger.info(f"{'='*70}\n")
                
                self.results = videos[:max_videos]
                
            except Exception as e:
                logger.error(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
                self.update_crawler_job(job_id, 'failed', error_message=str(e))
                
            finally:
                try:
                    await browser.close()
                except:
                    pass
        
        return self.results
    
    async def check_video_availability(self, page, video_url):
        """Kiểm tra xem video còn tồn tại hay không bằng cách truy cập trực tiếp"""
        try:
            # Mở tab mới để không làm mất trang hashtag đang crawl
            context = page.context
            new_page = await context.new_page()
            
            # Truy cập link video với timeout 20 giây
            response = await new_page.goto(video_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(random.uniform(1, 2)) # Chờ 1 chút cho load xong

            # Kiểm tra trạng thái HTTP hoặc sự xuất hiện của trình phát video
            # Nếu status là 404 hoặc có text báo video không tồn tại
            content = await new_page.content()
            is_available = True
            
            if response.status == 404 or "Video currently unavailable" in content or "Video này không hiển thị" in content:
                is_available = False
                logger.warning(f"🚫 Video chết hoặc bị chặn: {video_url}")
            
            await new_page.close() # Đóng tab kiểm tra
            return is_available
        except Exception as e:
            logger.error(f"⚠️ Lỗi khi check link {video_url}: {e}")
            return False
    async def smart_browser_validator(self, context, video_links, limit=5):
        """
        Kiểm tra ngẫu nhiên một vài link trong danh sách bằng chính Browser hiện tại
        Return: True/False (not list)
        """
        if not video_links:
            return False  # ✅ FIX: Return False, not []
        
        valid_count = 0
        test_pool = video_links[:limit] 
        
        check_page = await context.new_page()
        logger.info(f"🔍 Validating {len(test_pool)} links...")

        for link in test_pool:
            try:
                await check_page.goto(link, wait_until="domcontentloaded", timeout=60000)
                
                try:
                    await check_page.wait_for_selector("video", timeout=10000)
                    is_alive = await check_page.query_selector("video")
                except:
                    is_alive = None
                
                if is_alive:
                    logger.info(f"  ✅ Valid: {link[:100]}...")
                    valid_count += 1
                else:
                    logger.warning(f"  ❌ Invalid: {link[:100]}...")
                    
                await asyncio.sleep(random.uniform(2, 4))
                
            except Exception as e:
                logger.error(f"  ⚠️  Error: {e}")
        
        await check_page.close()
        
        # ✅ FIX: Return boolean
        success = valid_count >= 2  # At least 2 valid links
        
        if success:
            logger.info(f"✅ Validation passed ({valid_count}/{len(test_pool)} valid)\n")
        else:
            logger.warning(f"❌ Validation failed ({valid_count}/{len(test_pool)} valid)\n")
        
        return success

# Test
async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run TikTok hashtag crawler")

    parser.add_argument(
        "--hashtags",
        type=str,
        default="phoidonam,phoidonu,womenfashion,thoitrangnu",
        help="Comma-separated hashtags, example: y2k,vintage,streetwear,menoutfit,menfashion"
    )

    parser.add_argument(
        "--max-videos",
        type=int,
        default=500,
        help="Maximum videos per hashtag"
    )

    parser.add_argument(
        "--max-scrolls",
        type=int,
        default=40,
        help="Maximum scrolls per hashtag"
    )

    parser.add_argument(
        "--cookies-file",
        type=str,
        default="cookies.json",
        help="Path to cookies file"
    )

    args = parser.parse_args()

    hashtags = [
        item.strip().replace("#", "")
        for item in args.hashtags.split(",")
        if item.strip()
    ]

    crawler = HashtagCrawlerWithCookies(cookies_file=args.cookies_file)

    try:
        for hashtag in hashtags:
            logger.info("=" * 70)
            logger.info(f"🚀 Admin crawler started for #{hashtag}")
            logger.info(f"📌 max_videos={args.max_videos}, max_scrolls={args.max_scrolls}")
            logger.info("=" * 70)

            await crawler.crawl_hashtag(
                hashtag=hashtag,
                max_videos=args.max_videos,
                max_scrolls=args.max_scrolls
            )

    finally:
        try:
            crawler.db.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())