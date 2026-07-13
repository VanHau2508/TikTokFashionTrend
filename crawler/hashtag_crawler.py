from playwright.async_api import async_playwright
import asyncio
import logging
import json
import os
from datetime import datetime
from database.config import SessionLocal
from crawler.base_crawler import BaseCrawler
from dotenv import load_dotenv
import random

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HashtagCrawler(BaseCrawler):
    """Crawl videos from TikTok hashtags using Cookies"""
    
    def __init__(self, cookies_file='cookies.json'):
        db = SessionLocal()
        super().__init__(db)
        self.cookies_file = cookies_file
        self.cookies = self._load_cookies()
        self.results = []
    
    def _load_cookies(self):
        """Load cookies từ file"""
        try:
            if not os.path.exists(self.cookies_file):
                logger.warning(f"⚠️  Cookies file not found: {self.cookies_file}")
                logger.info("💡 Continuing without cookies (may hit CAPTCHA)")
                return []
            
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            logger.info(f"✅ Loaded {len(cookies)} cookies from {self.cookies_file}")
            return cookies
            
        except Exception as e:
            logger.error(f"❌ Error loading cookies: {e}")
            return []
    
    async def crawl_hashtag(self, hashtag, max_videos=100, max_scrolls=10):
        """
        Crawl videos from hashtag (sử dụng cookies để bypass CAPTCHA)
        """
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🎯 Crawling: #{hashtag}")
        logger.info(f"   Target: {max_videos} videos | Scrolls: {max_scrolls}")
        if self.cookies:
            logger.info(f"🍪 Using {len(self.cookies)} cookies")
        logger.info(f"{'='*70}")
        
        # Create job record
        job_id = self.create_crawler_job(
            job_name=f"Crawl hashtag: #{hashtag}",
            job_type='hashtag',
            parameters={'hashtag': hashtag, 'max_videos': max_videos, 'with_cookies': bool(self.cookies)}
        )
        
        async with async_playwright() as p:
            try:
                logger.info("🌐 Launching browser...")
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                    ]
                )
                
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='vi-VN',
                    timezone_id='Asia/Ho_Chi_Minh',
                    # Added: Better stealth settings
                    extra_http_headers={
                        'Accept-Language': 'vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Referer': 'https://www.tiktok.com/',
                        'DNT': '1',
                    }
                )
                
                # Inject multiple anti-detection scripts
                await context.add_init_script("""
                    // Hide webdriver
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Spoof plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });
                    
                    // Spoof Languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['vi-VN', 'vi', 'en-US', 'en'],
                    });
                    
                    // Remove chrome object
                    window.chrome = {
                        runtime: {}
                    };
                    
                    // Random canvas fingerprint
                    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
                    HTMLCanvasElement.prototype.toDataURL = function() {
                        if (this.width === 280 && this.height === 60) {
                            return 'data:image/png;base64,randomized';
                        }
                        return originalToDataURL.apply(this, arguments);
                    };
                """)
                
                # Inject cookies BEFORE navigating
                if self.cookies:
                    try:
                        await context.add_cookies(self.cookies)
                        logger.info("🍪 Cookies injected successfully!")
                    except Exception as e:
                        logger.warning(f"⚠️  Could not inject cookies: {e}")
                
                page = await context.new_page()
                
                # Random delay to avoid pattern detection
                await asyncio.sleep(random.uniform(2, 5))
                
                # Navigate to hashtag
                url = f"https://www.tiktok.com/tag/{hashtag}"
                logger.info(f"🔗 Navigating to: {url}")
                
                try:
                    response = await page.goto(url, wait_until='load', timeout=45000)
                    logger.info(f"✅ Response status: {response.status}")
                except Exception as e:
                    logger.warning(f"⚠️  Navigation warning: {e}")
                    # Continue anyway - page might still be usable
                
                # Wait for content with additional timeout
                try:
                    await page.wait_for_load_state('networkidle', timeout=10000)
                except:
                    logger.info("⏳ Skipped networkidle - continuing anyway")
                
                await asyncio.sleep(random.uniform(3, 6))  # Wait for JavaScript to render
                
                # Try to close any modal dialogs that might be blocking content
                try:
                    logger.info("🔍 Checking for modal dialogs...")
                    
                    # Try clicking close button first
                    close_buttons = [
                        'button[aria-label="Close"]',
                        'button[class*="close"]',
                        'div[role="dialog"] button',
                    ]
                    
                    for selector in close_buttons:
                        try:
                            button = await page.query_selector(selector)
                            if button:
                                await button.click(timeout=2000)
                                logger.info(f"   ✓ Clicked close button")
                                await asyncio.sleep(1)
                                break
                        except:
                            continue
                    
                    # Force remove modal overlay using JavaScript
                    await page.evaluate("""
                        () => {
                            // Remove any modal overlays
                            const modals = document.querySelectorAll('[role="dialog"]');
                            modals.forEach(m => m.remove());
                            
                            // Remove backdrop
                            const backdrops = document.querySelectorAll('[class*="backdrop"]');
                            backdrops.forEach(b => b.remove());
                            
                            // Remove body overflow hidden
                            document.body.style.overflow = 'auto';
                        }
                    """)
                    logger.info("   ✓ Removed modals via JavaScript")
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.info(f"   Note: Modal handling - {type(e).__name__}")
                
                # Check for CAPTCHA with more robust detection
                page_content = await page.content()
                
                logger.info(f"   Page content size: {len(page_content)} bytes")
                
                # Better CAPTCHA detection (only real hcaptcha/recaptcha challenges)
                has_hcaptcha = 'hcaptcha' in page_content.lower()
                has_recaptcha = 'recaptcha' in page_content.lower() and 'google' in page_content.lower()
                
                if has_hcaptcha or has_recaptcha:
                    logger.warning("⚠️  Real CAPTCHA challenge detected!")
                    await page.screenshot(path=f'debug_{hashtag}_captcha.png')
                    self.update_crawler_job(job_id, 'failed', error_message='CAPTCHA challenge detected')
                    await browser.close()
                    return []
                
                # If we got here, page should be usable - proceed to scrolling
                logger.info(f"✓ Page verified - proceeding to extract")
                
                # Scroll to load videos with random delays
                logger.info(f"📜 Scrolling to load videos...")
                for i in range(max_scrolls):
                    scroll_amount = random.randint(800, 1200)
                    await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                    await asyncio.sleep(random.uniform(2.5, 4.5))
                    logger.info(f"   ⏬ Scroll {i+1}/{max_scrolls}")
                
                # Wait a bit more for lazy-loaded content
                await asyncio.sleep(random.uniform(2, 3))
                
                # Extract video data with UPDATED SELECTORS
                logger.info(f"📦 Extracting video data...")
                
                # First, let's debug what's on the page
                try:
                    debug_info = await page.evaluate("""
                        () => {
                            return {
                                videoLinks: document.querySelectorAll('a[href*="/video/"]').length,
                                allLinks: document.querySelectorAll('a').length,
                                dataElements: document.querySelectorAll('[data-e2e]').length,
                                sampleDataElements: Array.from(document.querySelectorAll('[data-e2e]')).slice(0, 3).map(el => ({
                                    tag: el.tagName,
                                    attr: el.getAttribute('data-e2e'),
                                    href: el.href || el.querySelector('a')?.href || null,
                                    text: el.textContent?.substring(0, 50)
                                }))
                            };
                        }
                    """)
                    logger.info(f"📊 Page structure: {debug_info}")
                except Exception as e:
                    logger.warning(f"Debug failed: {e}")
                
                videos = await page.evaluate(r"""
                    () => {
                        const results = [];
                        
                        // Primary: Look in data-e2e elements
                        const dataElements = document.querySelectorAll('[data-e2e]');
                        
                        // Try all approaches to find video links
                        let videoLinks = [];
                        
                        // Approach 1: Direct /video/ links
                        videoLinks = Array.from(document.querySelectorAll('a[href*="/video/"]'));
                        
                        // Approach 2: If no direct links, search data-e2e elements for video URLs
                        if (videoLinks.length === 0) {
                            dataElements.forEach(elem => {
                                const href = elem.href || elem.querySelector('a')?.href;
                                if (href && href.includes('/video/')) {
                                    videoLinks.push(elem.querySelector('a') || elem);
                                }
                            });
                        }
                        
                        // Approach 3: Find anything with video IDs in data attributes
                        if (videoLinks.length === 0) {
                            dataElements.forEach(elem => {
                                const allText = elem.textContent + elem.innerHTML;
                                const match = allText.match(/\d{15,}/);  // Video IDs are 13-18 digits
                                if (match) {
                                    videoLinks.push(elem);
                                }
                            });
                        }
                        
                        // Process each video link
                        const processedIds = new Set();
                        
                        videoLinks.forEach((linkElem, idx) => {
                            try {
                                const videoUrl = linkElem.href;
                                const match = videoUrl.match(/video\/(\\d+)/);
                                const videoId = match ? match[1] : '';
                                
                                // Skip duplicates
                                if (!videoId || processedIds.has(videoId)) return;
                                processedIds.add(videoId);
                                
                                // Get parent container to extract metadata
                                let container = linkElem.closest('[data-e2e]') || linkElem.closest('div[class]') || linkElem;
                                
                                // Extract description from various sources
                                let description = '';
                                let author = '';
                                
                                // Try to get description
                                const descTexts = container.innerText || linkElem.innerText || '';
                                if (descTexts.length > 0) {
                                    const lines = descTexts.split('\\n').filter(l => l.trim().length > 3);
                                    description = lines[0] || 'No description';
                                    if (lines.length > 1 && lines[1].startsWith('@')) {
                                        author = lines[1].replace('@', '').trim();
                                    }
                                }
                                
                                // Fallback: get text content
                                if (!description) {
                                    description = container.textContent?.substring(0, 100) || 'No description';
                                }
                                
                                results.push({
                                    video_id: videoId,
                                    video_url: videoUrl,
                                    description: description,
                                    author: author || 'Unknown',
                                    views_text: 'N/A',
                                    likes_text: 'N/A'
                                });
                                
                            } catch (e) {
                                console.error(`Error processing link ${idx}:`, e.message);
                            }
                        });
                        
                        console.log(`Extracted ${results.length} unique videos`);
                        return results;
                    }
                """)
                
                logger.info(f"✅ Found {len(videos)} videos!")
                
                # Save to database
                videos_saved = 0
                for video in videos[:max_videos]:
                    try:
                        # Save user
                        tiktok_user_id = self.upsert_tiktok_user({
                            'unique_id': video['author'],
                            'nickname': video['author']
                        })
                        
                        if not tiktok_user_id:
                            continue
                        
                        # Save video
                        video_id = self.upsert_video({
                            'video_id': video['video_id'],
                            'description': video['description'],
                            'video_url': video['video_url'],
                            'cover_url': video['video_url']
                        }, tiktok_user_id)
                        
                        if not video_id:
                            continue
                        
                        # Save stats
                        self.insert_video_stats(video_id, {
                            'view_count': self._parse_number(video['views_text']),
                            'like_count': self._parse_number(video['likes_text'])
                        })
                        
                        # Save hashtags
                        hashtags = self._extract_hashtags(video['description'])
                        for tag in hashtags:
                            self.upsert_hashtag(tag.lstrip('#'), 'general')
                        
                        videos_saved += 1
                        
                    except Exception as e:
                        logger.error(f"   ❌ Error saving video: {e}")
                
                # Update job
                self.update_crawler_job(job_id, 'completed', videos_collected=videos_saved)
                
                logger.info(f"{'='*70}")
                logger.info(f"✅ Crawl complete: {videos_saved}/{max_videos} videos saved")
                logger.info(f"{'='*70}\n")
                
                self.results = videos[:max_videos]
                
            except Exception as e:
                logger.error(f"❌ Crawl error: {e}")
                import traceback
                traceback.print_exc()
                self.update_crawler_job(job_id, 'failed', error_message=str(e))
                
            finally:
                try:
                    await browser.close()
                except:
                    pass
        
        return self.results


# Test
async def main():
    crawler = HashtagCrawler(cookies_file='cookies.json')
    
    hashtags = ['thờitrang', 'ootd', 'streetwear']
    
    for hashtag in hashtags:
        results = await crawler.crawl_hashtag(
            hashtag=hashtag,
            max_videos=50,
            max_scrolls=5
        )
        logger.info(f"✅ {len(results)} videos from #{hashtag}\n")
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())