import pandas as pd
from sqlalchemy import create_engine

DB_URL = "postgresql://postgres:123456@localhost:5432/TikTokFashionTrend"
engine = create_engine(DB_URL)

START_DATE = "2026-05-09"
END_DATE = "2026-05-19"
MIN_HISTORY_POINTS = 5

query = f"""
WITH usable_hashtags AS (
    SELECT
        th.hashtag_id
    FROM trend_history th
    JOIN hashtags h ON h.hashtag_id = th.hashtag_id
    WHERE th.date BETWEEN '{START_DATE}' AND '{END_DATE}'
      AND LOWER(h.tag_name) NOT IN (
        'fyp',
        'fypシ',
        'foryou',
        'foryoupage',
        'viral',
        'trending',
        'trend',
        'xuhuong',
        'xh',
        'xhh',
        'xhhh',
        'foryouu',
        'fy',
        'review',
        'capcut',
        'tiktok',
        'viralvideo',
        'lyrics',
        'asian',
        'dancer',
        'sexy',
        'moodboard',
        'songs',
        'haihuoc',
        'tiktokgiaitri'
    )
    GROUP BY th.hashtag_id
    HAVING COUNT(DISTINCT th.date) >= {MIN_HISTORY_POINTS}
)
SELECT
    h.hashtag_id,
    h.tag_name,
    th.date,
    th.view_count,
    th.like_count,
    th.comment_count,
    th.share_count,
    th.video_count,
    th.engagement_rate,
    th.view_growth,
    th.like_growth,
    th.engagement_growth,
    th.trend_score
FROM trend_history th
JOIN hashtags h ON h.hashtag_id = th.hashtag_id
JOIN usable_hashtags uh ON uh.hashtag_id = th.hashtag_id
WHERE th.date BETWEEN '{START_DATE}' AND '{END_DATE}'
ORDER BY h.hashtag_id, th.date;
"""

df = pd.read_sql(query, engine)

print("=" * 80)
print("✅ EXPORT TREND_HISTORY FOR LSTM V2")
print("=" * 80)
print(f"Rows: {len(df)}")
print(f"Hashtags: {df['hashtag_id'].nunique() if len(df) > 0 else 0}")
print(f"Date range: {df['date'].min() if len(df) > 0 else None} → {df['date'].max() if len(df) > 0 else None}")

if len(df) == 0:
    raise ValueError("❌ Không có dữ liệu export. Kiểm tra lại trend_history hoặc MIN_HISTORY_POINTS.")

history_points = (
    df.groupby(["hashtag_id", "tag_name"])["date"]
    .nunique()
    .reset_index(name="history_points")
    .sort_values("history_points", ascending=False)
)

print("\n📌 History points distribution:")
print(history_points["history_points"].describe())
print("\n📌 Top hashtags:")
print(history_points.head(20))

output_file = "trend_history_lstm_v2_2026_05_09_to_2026_05_19.csv"
df.to_csv(output_file, index=False, encoding="utf-8-sig")

print(f"\n✅ Đã xuất file: {output_file}")