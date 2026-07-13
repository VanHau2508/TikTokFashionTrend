from apscheduler.schedulers.background import BackgroundScheduler
from crawler.hashtag_crawler_with_cookies import HashtagCrawlerWithCookies
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def crawl_task():
    """Scheduled crawling task"""
    logger.info(f"\n{'='*70}")
    logger.info(f"🚀 Scheduled Crawl: {datetime.now()}")
    logger.info(f"{'='*70}")
    
    try:
        crawler = HashtagCrawlerWithCookies(cookies_file='cookies.json')
        
        # Các hashtags để crawl
        hashtags = [
            'thờitrang', 'ootd', 'phoidonam', 'phoido2026', 'phoidonu',
            'fashionvietnam', 'fashiontrend', 'style', 'casual', 'fashion2026', 'clothes',
            'outfit', 'myoutfit', 'style2026'
        ]

        total_videos = 0
        
        async def run_crawl():
            nonlocal total_videos
            for hashtag in hashtags:
                try:
                    results = asyncio.run(
                        crawler.crawl_hashtag(
                            hashtag=hashtag,
                            max_videos=50,
                            max_scrolls=5
                        )
                    )
                    total_videos += len(results)
                    logger.info(f"✅ {len(results)} videos from #{hashtag}")
                    
                    import time
                    time.sleep(10)
                    
                except Exception as e:
                    logger.error(f"❌ Error: {e}")
        
        asyncio.run(run_crawl())
        
        logger.info(f"\n✅ Task completed: {total_videos} videos")
        
    except Exception as e:
        logger.error(f"❌ Task error: {e}")

def start_scheduler():
    """Start scheduler"""
    scheduler = BackgroundScheduler()
    
    # Run every 12 hours
    scheduler.add_job(
        crawl_task,
        'interval',
        hours=12,
        id='crawl_hashtags',
        name='Crawl TikTok hashtags'
    )
    
    # Run daily at 2 AM
    scheduler.add_job(
        crawl_task,
        'cron',
        hour=2,
        minute=0,
        id='daily_crawl',
        name='Daily crawl at 2 AM'
    )
    
    scheduler.start()
    logger.info("✅ Scheduler started!")
    logger.info(f"   Jobs: {len(scheduler.get_jobs())}")
    for job in scheduler.get_jobs():
        logger.info(f"   - {job.name}: {job.trigger}")
    
    return scheduler

if __name__ == "__main__":
    logger.info("🎯 TikTok Crawler Scheduler - PRODUCTION MODE")
    logger.info("📌 Auto-crawling enabled")
    
    # Start scheduler
    scheduler = start_scheduler()
    
    try:
        logger.info("⏳ Scheduler running... Press Ctrl+C to stop")
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("⛔ Shutting down scheduler...")
        scheduler.shutdown()
        logger.info("✅ Done!")