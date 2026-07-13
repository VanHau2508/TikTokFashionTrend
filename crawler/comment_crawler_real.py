from playwright.async_api import async_playwright
import asyncio
import logging
import json
from datetime import datetime, timezone
from database.config import SessionLocal
from database.models import Video, Comment
from dotenv import load_dotenv
import os

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealCommentCrawler:
    """Crawl thực tế comments từ video detail pages"""
    
    def __init__(self, cookies_file='cookies.json'):
        self.cookies_file = cookies_file
        self.cookies = self._load_cookies()
    
    def _load_cookies(self):
        """Load cookies"""
        try:
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            logger.info(f"✅ Loaded {len(cookies)} cookies")
            return cookies
        except:
            logger.warning("⚠️  No cookies found")
            return []
    
    async def crawl_video_comments(self, video_id, video_url, max_comments=20):
        """Crawl comments từ 1 video"""
        
        logger.info(f"\n📹 Crawling comments: {video_id}")
        
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(
                    headless=False,
                    args=['--disable-blink-features=AutomationControlled']
                )
                
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                # Add cookies
                if self.cookies:
                    try:
                        await context.add_cookies(self.cookies)
                    except:
                        pass
                
                page = await context.new_page()
                
                # Navigate to video
                logger.info(f"   🔗 Loading: {video_url}")
                response = await page.goto(video_url, wait_until='domcontentloaded', timeout=30000)
                logger.info(f"   ✅ Status: {response.status}")
                
                await asyncio.sleep(10)
                
                # Scroll để load comments
                logger.info(f"   📜 Scrolling to load comments...")
                for i in range(5):  # Scroll 5 lần
                    await page.evaluate("window.scrollBy(0, 800)")
                    await asyncio.sleep(3)
                    logger.info(f"      ⏬ Scroll {i+1}/5")
                
                # Extract comments
                logger.info(f"   📦 Extracting comments...")
                
                comments = await page.evaluate("""
                    () => {
                        const results = [];
                        
                        // TikTok comment selectors (có thể thay đổi)
                        const selectors = [
                            '[data-e2e="comment-item-content"]',
                            '[class*="CommentItemContent"]',
                            '[class*="comment-item-text"]',
                        ];
                        
                        let commentElements = [];
                        for (const selector of selectors) {
                            commentElements = document.querySelectorAll(selector);
                            if (commentElements.length > 0) break;
                        }
                        
                        console.log(`Found ${commentElements.length} comments`);
                        
                        commentElements.forEach((elem) => {
                            try {
                                const text = elem.innerText || elem.textContent;
                                
                                if (text && text.trim().length > 0 && text.trim().length < 500) {
                                    results.push({
                                        content: text.trim(),
                                        author: 'unknown',
                                        created_at: new Date().toISOString()
                                    });
                                }
                            } catch (e) {
                                console.error('Parse error:', e);
                            }
                        });
                        
                        return results;
                    }
                """)
                
                logger.info(f"   ✅ Found {len(comments)} comments")
                
                # Save to database
                db = SessionLocal()
                comments_saved = 0
                
                for comment_data in comments[:max_comments]:
                    try:
                        comment = Comment(
                            video_id=video_id,
                            commenter_id=comment_data.get('author', 'unknown'),
                            content=comment_data['content'],
                            like_count=0,
                            created_date=datetime.now(timezone.utc)
                        )
                        db.add(comment)
                        comments_saved += 1
                    except Exception as e:
                        logger.error(f"      ❌ Error: {e}")
                
                db.commit()
                db.close()
                
                logger.info(f"   💾 Saved {comments_saved} comments")
                
                await browser.close()
                
                return comments_saved
                
            except Exception as e:
                logger.error(f"   ❌ Error: {e}")
                return 0
    
    async def crawl_all_video_comments(self, limit=100, comments_per_video=20):
        """Crawl comments từ nhiều videos"""
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🧡 REAL COMMENT CRAWLER")
        logger.info(f"   Target: {limit} videos")
        logger.info(f"   Comments per video: {comments_per_video}")
        logger.info(f"{'='*70}")
        
        db = SessionLocal()
        
        try:
            # Get videos without comments
            videos = db.query(Video).limit(limit).all()
            
            logger.info(f"📊 Total videos: {len(videos)}")
            
            total_comments = 0
            
            for idx, video in enumerate(videos, 1):
                try:
                    # Construct video URL
                    video_url = video.video_url
                    
                    if not video_url:
                        logger.warning(f"   ⚠️  No URL for video {video.video_id}")
                        continue
                    
                    # Crawl comments
                    comments = await self.crawl_video_comments(
                        video_id=video.video_id,
                        video_url=video_url,
                        max_comments=comments_per_video
                    )
                    
                    total_comments += comments
                    
                    if idx % 10 == 0:
                        logger.info(f"\n✅ Progress: {idx}/{len(videos)} videos")
                        logger.info(f"   Total comments: {total_comments}")
                    
                    # Delay to avoid rate limit
                    await asyncio.sleep(10)
                    
                except Exception as e:
                    logger.error(f"❌ Error processing video {video.video_id}: {e}")
                    await asyncio.sleep(10)
            
            logger.info(f"\n{'='*70}")
            logger.info(f"✅ CRAWLING COMPLETE!")
            logger.info(f"   Videos processed: {len(videos)}")
            logger.info(f"   Total comments: {total_comments}")
            logger.info(f"{'='*70}\n")
            
        finally:
            db.close()

async def main():
    crawler = RealCommentCrawler(cookies_file='cookies.json')
    await crawler.crawl_all_video_comments(limit=50, comments_per_video=20)

if __name__ == "__main__":
    asyncio.run(main())