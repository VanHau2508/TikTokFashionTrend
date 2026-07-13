"""
Trend Detection Engine
- Detect trending fashion items & hashtags
- Calculate growth rates
- Identify emerging trends
"""

import logging
from datetime import datetime, timedelta, timezone
from database.config import SessionLocal
from database.models import Hashtag, Video, VideoStat
from sqlalchemy import func, cast, Float, desc, and_
import statistics
from sqlalchemy.orm import aliased
from ai.tag_filters import BLACKLIST_TAGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TrendDetector:
    """Detect fashion trends from data"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    def calculate_growth_rate(self, current_value, previous_value):
        """Calculate growth rate percentage"""
        
        if previous_value == 0:
            return 0 if current_value == 0 else 100
        
        return ((current_value - previous_value) / previous_value) * 100
    
    def get_hashtag_growth_by_range(self, start_time, end_time):
        """
        Tính growth của từng hashtag trong một khoảng thời gian.
        Chỉ dùng video đã YOLO success.
        """

        from database.models import video_hashtags

        try:
            # Bước 1: Tính growth từng video trong khoảng thời gian
            video_growth_subquery = self.db.query(
                Hashtag.hashtag_id.label("hashtag_id"),
                Hashtag.tag_name.label("tag_name"),
                Hashtag.category.label("category"),
                Video.video_id.label("video_id"),

                (
                    func.max(VideoStat.view_count) - func.min(VideoStat.view_count)
                ).label("view_growth"),

                (
                    func.max(VideoStat.like_count) - func.min(VideoStat.like_count)
                ).label("like_growth"),

                (
                    func.max(VideoStat.comment_count) - func.min(VideoStat.comment_count)
                ).label("comment_growth"),

                (
                    func.max(VideoStat.share_count) - func.min(VideoStat.share_count)
                ).label("share_growth")
            ).join(
                video_hashtags,
                Hashtag.hashtag_id == video_hashtags.c.hashtag_id
            ).join(
                Video,
                video_hashtags.c.video_id == Video.video_id
            ).join(
                VideoStat,
                Video.video_id == VideoStat.video_id
            ).filter(
                VideoStat.collected_at >= start_time
            ).filter(
                VideoStat.collected_at < end_time
            ).filter(
                Video.processing_status == "success"
            ).filter(
                ~func.lower(Hashtag.tag_name).in_(list(BLACKLIST_TAGS))
            ).group_by(
                Hashtag.hashtag_id,
                Hashtag.tag_name,
                Hashtag.category,
                Video.video_id
            ).subquery()

            # Bước 2: Tổng hợp growth theo hashtag
            results = self.db.query(
                video_growth_subquery.c.hashtag_id,
                video_growth_subquery.c.tag_name,
                video_growth_subquery.c.category,
                func.count(func.distinct(video_growth_subquery.c.video_id)).label("video_count"),
                cast(func.sum(video_growth_subquery.c.view_growth), Float).label("total_view_growth"),
                cast(func.sum(video_growth_subquery.c.like_growth), Float).label("total_like_growth"),
                cast(func.sum(video_growth_subquery.c.comment_growth), Float).label("total_comment_growth"),
                cast(func.sum(video_growth_subquery.c.share_growth), Float).label("total_share_growth")
            ).group_by(
                video_growth_subquery.c.hashtag_id,
                video_growth_subquery.c.tag_name,
                video_growth_subquery.c.category
            ).all()

            stats = []

            for r in results:
                view_growth = r.total_view_growth or 0
                like_growth = r.total_like_growth or 0
                comment_growth = r.total_comment_growth or 0
                share_growth = r.total_share_growth or 0

                engagement_growth = like_growth + comment_growth + share_growth

                stats.append({
                    "hashtag_id": r.hashtag_id,
                    "hashtag": r.tag_name,
                    "category": r.category,
                    "video_count": r.video_count,
                    "view_growth": view_growth,
                    "like_growth": like_growth,
                    "comment_growth": comment_growth,
                    "share_growth": share_growth,
                    "engagement_growth": engagement_growth
                })

            return stats

        except Exception as e:
            logger.error(f"Lỗi khi tính hashtag growth by range: {e}")
            return []
        
    def get_hashtag_stats(self, days_back=7):
        """
        Lấy top trending hashtag dựa trên snapshot mới nhất của mỗi video.
        Chỉ lấy video đã được YOLO xác nhận: processing_status = 'success'
        """

        logger.info(f"\n📊 Đang phân tích Hashtags - {days_back} ngày gần nhất\n")

        from database.models import video_hashtags

        start_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        try:
            LatestStat = aliased(VideoStat)

            latest_stat_subquery = self.db.query(
                VideoStat.video_id.label("video_id"),
                func.max(VideoStat.collected_at).label("latest_collected_at")
            ).filter(
                VideoStat.collected_at >= start_date
            ).group_by(
                VideoStat.video_id
            ).subquery()

            results = self.db.query(
                Hashtag.hashtag_id,
                Hashtag.tag_name,
                Hashtag.category,
                func.count(func.distinct(Video.video_id)).label("video_count"),
                cast(func.sum(LatestStat.view_count), Float).label("total_views"),
                cast(func.sum(LatestStat.like_count), Float).label("total_likes"),
                cast(func.sum(LatestStat.comment_count), Float).label("total_comments"),
                cast(func.sum(LatestStat.share_count), Float).label("total_shares")
            ).join(
                video_hashtags,
                Hashtag.hashtag_id == video_hashtags.c.hashtag_id
            ).join(
                Video,
                video_hashtags.c.video_id == Video.video_id
            ).join(
                latest_stat_subquery,
                latest_stat_subquery.c.video_id == Video.video_id
            ).join(
                LatestStat,
                and_(
                    LatestStat.video_id == latest_stat_subquery.c.video_id,
                    LatestStat.collected_at == latest_stat_subquery.c.latest_collected_at
                )
            ).filter(
                Video.processing_status == "success"
            ).filter(
                ~func.lower(Hashtag.tag_name).in_(list(BLACKLIST_TAGS))
            ).group_by(
                Hashtag.hashtag_id,
                Hashtag.tag_name,
                Hashtag.category
            ).all()

            hashtag_stats = []

            for r in results:
                views = r.total_views or 0
                likes = r.total_likes or 0
                comments = r.total_comments or 0
                shares = r.total_shares or 0

                engagement_rate = ((likes + comments + shares) / (views + 1)) * 100

                hashtag_stats.append({
                    "hashtag_id": r.hashtag_id,
                    "hashtag": r.tag_name,
                    "video_count": r.video_count,
                    "total_views": views,
                    "total_likes": likes,
                    "total_comments": comments,
                    "total_shares": shares,
                    "engagement_rate": engagement_rate,
                    "category": r.category
                })

            hashtag_stats.sort(key=lambda x: x["total_views"], reverse=True)

            return hashtag_stats

        except Exception as e:
            logger.error(f"Lỗi khi phân tích hashtag stats: {e}")
            return []
        
    def detect_trending_items(self, top_n=20):
        """Detect top trending items"""
        
        logger.info("\n" + "="*70)
        logger.info("🔥 TREND DETECTION - TOP ITEMS")
        logger.info("="*70 + "\n")
        
        hashtag_stats = self.get_hashtag_stats(days_back=7)
        
        if not hashtag_stats:
            logger.warning("No hashtag data found")
            return []
        
        # Get top N by views
        top_items = hashtag_stats[:top_n]
        
        logger.info(f"📈 TOP {len(top_items)} TRENDING HASHTAGS:\n")
        
        trends = []
        
        for idx, item in enumerate(top_items, 1):
            logger.info(f"[{idx}] #{item['hashtag']}")
            logger.info(f"     Videos: {item['video_count']}")
            logger.info(f"     Views: {item['total_views']:,}")
            logger.info(f"     Likes: {item['total_likes']:,}")
            logger.info(f"     Engagement: {item['engagement_rate']:.2f}%\n")
            
            trends.append({
                'rank': idx,
                'hashtag': item['hashtag'],
                'video_count': item['video_count'],
                'views': item['total_views'],
                'likes': item['total_likes'],
                'engagement_rate': round(item['engagement_rate'], 2),
                'category': item['category'],
                'trend_score': (float(item['total_views']) * 0.2) + (float(item['total_likes']) * 0.8),
                'detected_at': datetime.now(timezone.utc).isoformat()
            })
        
        return trends
    
    def detect_emerging_trends(self, min_growth_rate=20, limit=50):
        """
        Detect emerging trends bằng cách so sánh:
        - 24h gần nhất
        - 24h trước đó
        """

        logger.info("\n" + "=" * 70)
        logger.info("🚀 EMERGING TRENDS DETECTION")
        logger.info("=" * 70 + "\n")

        now = datetime.now(timezone.utc)

        current_start = now - timedelta(hours=24)
        previous_start = now - timedelta(hours=48)
        previous_end = current_start

        current_stats = self.get_hashtag_growth_by_range(current_start, now)
        previous_stats = self.get_hashtag_growth_by_range(previous_start, previous_end)

        emerging = []

        for current in current_stats:
            hashtag = current["hashtag"]

            previous = next(
                (p for p in previous_stats if p["hashtag_id"] == current["hashtag_id"]),
                None
            )

            if not previous:
                continue

            previous_growth = previous["view_growth"]
            current_growth = current["view_growth"]

            if previous_growth <= 0:
                continue

            growth_rate = self.calculate_growth_rate(
                current_growth,
                previous_growth
            )

            min_video_count = 5
            min_previous_growth = 1000
            min_current_growth = 5000

            if (
                growth_rate >= min_growth_rate
                and current["video_count"] >= min_video_count
                and previous_growth >= min_previous_growth
                and current_growth >= min_current_growth
            ):
                trend_score = (
                    current["view_growth"] * 0.5
                    + current["like_growth"] * 0.3
                    + current["comment_growth"] * 0.1
                    + current["share_growth"] * 0.1
                )

                emerging.append({
                    "hashtag_id": current["hashtag_id"],
                    "hashtag": hashtag,
                    "growth_rate": round(growth_rate, 2),
                    "current_24h_growth": current_growth,
                    "previous_24h_growth": previous_growth,
                    "video_count": current["video_count"],
                    "trend_score": round(trend_score, 2),
                    "detected_at": datetime.now(timezone.utc).isoformat()
                })

        emerging.sort(key=lambda x: x["trend_score"], reverse=True)       
        emerging = emerging[:limit]

        for item in emerging:
            logger.info(f"🚀 #{item['hashtag']}")
            logger.info(f"   Growth Rate: {item['growth_rate']}%")
            logger.info(f"   Current 24h Growth: {item['current_24h_growth']:,}")
            logger.info(f"   Previous 24h Growth: {item['previous_24h_growth']:,}")
            logger.info(f"   Videos: {item['video_count']}\n")

        return emerging
    
    def analyze_seasonal_patterns(self):
        """Analyze seasonal/weekly patterns"""
        
        logger.info("\n" + "="*70)
        logger.info("📅 SEASONAL PATTERN ANALYSIS")
        logger.info("="*70 + "\n")
        
        # Get videos by day of week
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        pattern_data = {}
        
        for idx, day in enumerate(days):
            # This is simplified - in production, extract from created_date
            pattern_data[day] = {
                'videos': 0,
                'avg_views': 0,
                'avg_engagement': 0
            }
        
        logger.info("📊 Videos by day of week:")
        logger.info("(In production, extract from actual dates)\n")
        
        return pattern_data
    
    def close(self):
        """Close database connection"""
        self.db.close()

def main():
    detector = TrendDetector()
    
    # Detect trending items
    top_trends = detector.detect_trending_items(top_n=20)
    
    # Detect emerging trends
    emerging = detector.detect_emerging_trends(min_growth_rate=20)      
    # Analyze patterns
    patterns = detector.analyze_seasonal_patterns()
    
    logger.info("\n" + "="*70)
    logger.info("✅ TREND DETECTION COMPLETE!")
    logger.info("="*70)
    logger.info(f"\n📊 Summary:")
    logger.info(f"   Top trends: {len(top_trends)}")
    logger.info(f"   Emerging: {len(emerging)}")
    logger.info(f"   Patterns: {len(patterns)}")
    
    detector.close()

if __name__ == "__main__":
    main()