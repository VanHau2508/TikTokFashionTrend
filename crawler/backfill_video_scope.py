"""
backfill_video_scope_2026_v3.py

Purpose:
- Backfill TikTok video publish date and analysis scope for existing and newly crawled videos.
- Default mode processes only videos that have not been scope-checked yet:
    published_at IS NULL AND exclude_reason IS NULL
- This prevents checked old videos from being rechecked every run.
- Use --force to rescan all matched videos when old data may have been filled incorrectly.
- Use --retry-unknown to retry videos previously marked unknown_publish_date.

Recommended workflow:
    python backfill_video_scope_2026_v3.py --fetch-missing --limit 300
    python backfill_video_scope_2026_v3.py --fetch-missing --force --limit 500
    python backfill_video_scope_2026_v3.py --fetch-missing --retry-unknown --limit 200
"""

import argparse
import asyncio
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from playwright.async_api import async_playwright
from database.config import SessionLocal
from database.models import Video

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_ANALYSIS_START_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def normalize_to_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_create_time(create_time):
    """Parse TikTok itemStruct.createTime. Usually Unix seconds; sometimes milliseconds."""
    if create_time is None:
        return None

    text = str(create_time).strip()
    if not re.fullmatch(r"\d{9,14}", text):
        return None

    ts = int(text)
    if ts > 10_000_000_000:  # milliseconds
        ts = ts / 1000

    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        return None

    now = datetime.now(timezone.utc)
    if dt.year < 2016 or dt > now + timedelta(days=1):
        return None

    return dt

def parse_tiktok_video_id_datetime(tiktok_video_id):
    """
    Parse TikTok publish time from the numeric video id.
    TikTok video ids commonly behave like Snowflake ids where the high bits
    contain a Unix timestamp. This avoids opening every video page when possible.
    """
    if not tiktok_video_id:
        return None

    text = str(tiktok_video_id).strip()
    if not re.fullmatch(r"\d{15,25}", text):
        return None

    try:
        ts = int(text) >> 32
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        return None

    now = datetime.now(timezone.utc)
    if dt.year < 2016 or dt > now + timedelta(days=1):
        return None

    return dt


def parse_publish_text(published_text, crawl_time=None, analysis_start_date=None):
    """
    Parse visible publish-date text:
    - 2025-11-27
    - 4-16
    - 2 ngày trước / 10 giờ trước / 1 tuần trước
    """
    crawl_time = normalize_to_utc(crawl_time) or datetime.now(timezone.utc)
    analysis_start_date = normalize_to_utc(analysis_start_date) or DEFAULT_ANALYSIS_START_DATE

    if not published_text:
        return {
            "published_at": None,
            "published_text": None,
            "date_confidence": "unknown",
            "is_in_scope": False,
            "exclude_reason": "unknown_publish_date",
        }

    raw = str(published_text).strip()
    text = raw.lower()
    published_at = None
    confidence = "unknown"

    try:
        full_date = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text)
        if full_date:
            y, m, d = map(int, full_date.groups())
            published_at = datetime(y, m, d, tzinfo=timezone.utc)
            confidence = "high"

        if published_at is None:
            # TikTok short date is normally month-day in the crawl year.
            short_date = re.search(r"\b(\d{1,2})[-/](\d{1,2})\b", text)
            if short_date:
                m, d = map(int, short_date.groups())
                y = crawl_time.year
                candidate = datetime(y, m, d, tzinfo=timezone.utc)
                if candidate.date() > (crawl_time + timedelta(days=1)).date():
                    candidate = datetime(y - 1, m, d, tzinfo=timezone.utc)
                published_at = candidate
                confidence = "medium"

        if published_at is None:
            relative_patterns = [
                (r"(\d+)\s*(giây|second|seconds)\s*(trước|ago)?", "seconds"),
                (r"(\d+)\s*(phút|minute|minutes|min)\s*(trước|ago)?", "minutes"),
                (r"(\d+)\s*(giờ|hour|hours|h)\s*(trước|ago)?", "hours"),
                (r"(\d+)\s*(ngày|day|days|d)\s*(trước|ago)?", "days"),
                (r"(\d+)\s*(tuần|week|weeks|w)\s*(trước|ago)?", "weeks"),
                (r"(\d+)\s*(tháng|month|months)\s*(trước|ago)?", "months"),
                (r"(\d+)\s*(năm|year|years|y)\s*(trước|ago)?", "years"),
            ]
            for pattern, unit in relative_patterns:
                match = re.search(pattern, text)
                if not match:
                    continue
                value = int(match.group(1))
                if unit == "seconds":
                    published_at = crawl_time - timedelta(seconds=value)
                elif unit == "minutes":
                    published_at = crawl_time - timedelta(minutes=value)
                elif unit == "hours":
                    published_at = crawl_time - timedelta(hours=value)
                elif unit == "days":
                    published_at = crawl_time - timedelta(days=value)
                elif unit == "weeks":
                    published_at = crawl_time - timedelta(weeks=value)
                elif unit == "months":
                    published_at = crawl_time - timedelta(days=value * 30)
                elif unit == "years":
                    published_at = crawl_time - timedelta(days=value * 365)
                confidence = "medium"
                break

        if published_at is None and ("hôm qua" in text or "yesterday" in text):
            published_at = crawl_time - timedelta(days=1)
            confidence = "medium"

        if published_at is None and ("vừa xong" in text or "just now" in text):
            published_at = crawl_time
            confidence = "medium"

    except Exception:
        published_at = None
        confidence = "unknown"

    if published_at is None:
        return {
            "published_at": None,
            "published_text": raw,
            "date_confidence": "unknown",
            "is_in_scope": False,
            "exclude_reason": "unknown_publish_date",
        }

    is_in_scope = published_at >= analysis_start_date
    return {
        "published_at": published_at,
        "published_text": raw,
        "date_confidence": confidence,
        "is_in_scope": is_in_scope,
        "exclude_reason": None if is_in_scope else "old_video_before_2026",
    }


def build_scope_data_from_datetime(published_at, published_text=None, confidence="high", analysis_start_date=None):
    analysis_start_date = normalize_to_utc(analysis_start_date) or DEFAULT_ANALYSIS_START_DATE
    published_at = normalize_to_utc(published_at)
    if not published_at:
        return {
            "published_at": None,
            "published_text": published_text,
            "date_confidence": "unknown",
            "is_in_scope": False,
            "exclude_reason": "unknown_publish_date",
        }

    is_in_scope = published_at >= analysis_start_date
    return {
        "published_at": published_at,
        "published_text": published_text or published_at.strftime("%Y-%m-%d"),
        "date_confidence": confidence,
        "is_in_scope": is_in_scope,
        "exclude_reason": None if is_in_scope else "old_video_before_2026",
    }


async def fetch_publish_metadata(context, video_url, max_retries=2):
    """
    Browser fallback only when video-id timestamp is unavailable.
    Uses a fresh page per retry to reduce ExecutionContextDestroyed errors.
    Priority:
    1) itemStruct.createTime from TikTok JSON state.
    2) visible date text from DOM body.
    """
    last_exc = None
    for attempt in range(1, max_retries + 1):
        page = await context.new_page()
        try:
            await page.goto(video_url, wait_until="domcontentloaded", timeout=60000)
            try:
                await page.wait_for_selector("#__UNIVERSAL_DATA_FOR_REHYDRATION__, #SIGI_STATE", timeout=8000)
            except Exception:
                pass
            await page.wait_for_timeout(2500)

            metadata = await page.evaluate(
            r"""
            () => {
                const out = { createTime: null, publishText: null, source: null };
                try {
                    const el = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__') ||
                               document.getElementById('SIGI_STATE');
                    if (el) {
                        const data = JSON.parse(el.textContent);
                        const item =
                            data.__DEFAULT_SCOPE__?.['webapp.video-detail']?.itemInfo?.itemStruct ||
                            data.ItemModule?.[Object.keys(data.ItemModule || {})[0]] ||
                            null;
                        if (item) {
                            out.createTime = item.createTime || item.create_time || null;
                            out.source = 'json_createTime';
                        }
                    }
                } catch (e) {}

                if (!out.createTime) {
                    const fullText = (document.body.innerText || '').replace(/\s+/g, ' ').trim();
                    const patterns = [
                        /\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b/,
                        /\b\d{1,2}[-/]\d{1,2}\b/,
                        /\b\d+\s*(giây|phút|giờ|ngày|tuần|tháng|năm)\s*trước\b/i,
                        /\b\d+\s*(second|seconds|minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years|h|d|w)\s*ago\b/i,
                        /\b(hôm qua|vừa xong|yesterday|just now)\b/i
                    ];
                    for (const pattern of patterns) {
                        const match = fullText.match(pattern);
                        if (match) {
                            out.publishText = match[0];
                            out.source = 'dom_text';
                            break;
                        }
                    }
                }
                return out;
            }
            """
        )
            return metadata or {}
        except Exception as exc:
            last_exc = exc
            logger.warning("Không lấy được ngày đăng từ %s (attempt %s/%s): %s", video_url, attempt, max_retries, exc)
            await asyncio.sleep(1.5 * attempt)
        finally:
            try:
                await page.close()
            except Exception:
                pass

    return {}


def apply_scope(video, scope_data):
    video.published_at = scope_data["published_at"]
    video.published_text = scope_data["published_text"]
    video.date_confidence = scope_data["date_confidence"]
    video.is_in_scope = scope_data["is_in_scope"]
    video.exclude_reason = scope_data["exclude_reason"]

    # Only overwrite created_date when date is from TikTok publish metadata.
    if scope_data["published_at"] is not None and scope_data["date_confidence"] in ("high", "medium"):
        video.created_date = scope_data["published_at"]


def build_query(db, args):
    query = db.query(Video)

    if args.force:
        # Rescan all matched videos. Use when previous backfill may be wrong.
        pass
    elif args.retry_unknown:
        query = query.filter(Video.exclude_reason == "unknown_publish_date")
    else:
        # Default: only never-checked videos. New crawler rows usually match this.
        query = query.filter(Video.published_at == None, Video.exclude_reason == None)

    if args.only_pending:
        query = query.filter(Video.processing_status == "pending")

    if args.newest_first:
        query = query.order_by(Video.collected_date.desc().nullslast(), Video.video_id.desc())
    else:
        query = query.order_by(Video.video_id.asc())

    if args.limit and args.limit > 0:
        query = query.limit(args.limit)

    return query


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-missing", action="store_true", help="Open video_url to fetch publish date.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum videos to process. 0 = all matched videos.")
    parser.add_argument("--cookies-file", type=str, default="cookies.json")
    parser.add_argument("--force", action="store_true", help="Rescan all matched videos, including already checked ones.")
    parser.add_argument("--retry-unknown", action="store_true", help="Retry videos previously marked unknown_publish_date.")
    parser.add_argument("--only-pending", action="store_true", help="Only process videos with processing_status='pending'.")
    parser.add_argument("--newest-first", action="store_true", default=True, help="Process newest crawled videos first.")
    parser.add_argument("--analysis-start-date", type=str, default="2026-01-01", help="YYYY-MM-DD. Default: 2026-01-01.")
    parser.add_argument("--commit-every", type=int, default=20)
    parser.add_argument("--delay", type=float, default=1.2, help="Delay between video page visits, seconds.")
    args = parser.parse_args()

    analysis_start_date = datetime.strptime(args.analysis_start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    db = SessionLocal()
    videos = build_query(db, args).all()
    logger.info("Tổng video cần kiểm tra: %s", len(videos))

    if not videos:
        db.close()
        return

    playwright = None
    browser = None
    context = None
    page = None

    try:
        if args.fetch_missing:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(locale="vi-VN", timezone_id="Asia/Ho_Chi_Minh")

            cookies_path = Path(args.cookies_file)
            if cookies_path.exists():
                try:
                    with cookies_path.open("r", encoding="utf-8") as f:
                        await context.add_cookies(json.load(f))
                    logger.info("Đã nạp cookies từ %s", args.cookies_file)
                except Exception as exc:
                    logger.warning("Không nạp được cookies: %s", exc)


        updated = 0
        in_scope = 0
        out_scope = 0
        unknown = 0
        fetched_json = 0
        fetched_dom = 0
        fetched_video_id = 0

        for idx, video in enumerate(videos, 1):
            scope_data = None

            # Best source for this project: TikTok numeric video id timestamp.
            # This is faster and more stable than opening every TikTok video page.
            id_dt = parse_tiktok_video_id_datetime(video.tiktok_video_id)
            if id_dt:
                fetched_video_id += 1
                scope_data = build_scope_data_from_datetime(
                    id_dt,
                    published_text=id_dt.strftime("%Y-%m-%d"),
                    confidence="high",
                    analysis_start_date=analysis_start_date,
                )

            # IMPORTANT: Do NOT use Video.created_date as a fallback.
            # In this project it may be collection time, not true TikTok publish time.
            if scope_data is None and video.published_at and not args.force:
                scope_data = build_scope_data_from_datetime(
                    video.published_at,
                    published_text=video.published_text,
                    confidence=video.date_confidence or "high",
                    analysis_start_date=analysis_start_date,
                )
            elif scope_data is None and video.published_text and not args.force:
                scope_data = parse_publish_text(
                    video.published_text,
                    crawl_time=video.collected_date or datetime.now(timezone.utc),
                    analysis_start_date=analysis_start_date,
                )

            if scope_data is None and args.fetch_missing and video.video_url and context is not None:
                metadata = await fetch_publish_metadata(context, video.video_url)
                create_dt = parse_create_time(metadata.get("createTime"))

                if create_dt:
                    fetched_json += 1
                    scope_data = build_scope_data_from_datetime(
                        create_dt,
                        published_text=create_dt.strftime("%Y-%m-%d"),
                        confidence="high",
                        analysis_start_date=analysis_start_date,
                    )
                elif metadata.get("publishText"):
                    fetched_dom += 1
                    scope_data = parse_publish_text(
                        metadata.get("publishText"),
                        crawl_time=video.collected_date or datetime.now(timezone.utc),
                        analysis_start_date=analysis_start_date,
                    )

                await asyncio.sleep(args.delay)

            if scope_data is None:
                scope_data = {
                    "published_at": None,
                    "published_text": None,
                    "date_confidence": "unknown",
                    "is_in_scope": False,
                    "exclude_reason": "unknown_publish_date",
                }

            apply_scope(video, scope_data)
            db.add(video)
            updated += 1

            if scope_data["is_in_scope"]:
                in_scope += 1
            elif scope_data["exclude_reason"] == "unknown_publish_date":
                unknown += 1
            else:
                out_scope += 1

            if updated % args.commit_every == 0:
                db.commit()
                logger.info(
                    "Đã cập nhật %s/%s | in_scope=%s | out_scope=%s | unknown=%s | id=%s | json=%s | dom=%s",
                    idx, len(videos), in_scope, out_scope, unknown, fetched_video_id, fetched_json, fetched_dom
                )

        db.commit()
        logger.info("Hoàn tất.")
        logger.info(
            "updated=%s | in_scope=%s | out_scope=%s | unknown=%s | id=%s | json=%s | dom=%s",
            updated, in_scope, out_scope, unknown, fetched_video_id, fetched_json, fetched_dom
        )

    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
