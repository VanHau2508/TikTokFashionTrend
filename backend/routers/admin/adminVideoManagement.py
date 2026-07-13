import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from math import ceil
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from backend.security import require_admin
from database.models import (
    AIAnalysis,
    FashionItem,
    Hashtag,
    Video,
    VideoStat,
    video_hashtags,
)

router = APIRouter(prefix="/api/admin/videos", tags=["Admin Video Management"])


# ============================================================
# Helpers
# ============================================================

SUCCESS_STATUS = "success"
FAILED_STATUSES = [
    "failed",
    "failed_no_fashion",
    "failed_no_frame",
    "failed_no_frame_final",
    "error",
]
ALL_KNOWN_STATUSES = [
    "success",
    "failed_no_fashion",
    "failed_no_frame",
    "failed_no_frame_final",
    "uncertain",
    "pending",
    "error",
    "failed",
]


STATUS_LABELS = {
    "success": "Hợp lệ",
    "failed_no_fashion": "Không phát hiện thời trang",
    "failed_no_frame": "Lỗi lấy khung hình",
    "failed_no_frame_final": "Lỗi lấy khung hình",
    "uncertain": "Chưa chắc chắn",
    "pending": "Đang chờ xử lý",
    "error": "Lỗi xử lý",
    "failed": "Thất bại",
}


class VideoIdListRequest(BaseModel):
    video_ids: list[int] = Field(default_factory=list)


class MarkScopeRequest(VideoIdListRequest):
    is_in_scope: bool
    reason: str | None = None


class DeleteVideosRequest(VideoIdListRequest):
    hard_delete: bool = False


class ResetYoloRequest(VideoIdListRequest):
    clear_old_results: bool = True


class UpdateVideoStatusRequest(BaseModel):
    processing_status: str
    is_analyzed: bool | None = None


class UpdateVideoScopeRequest(BaseModel):
    is_in_scope: bool
    reason: str | None = None


class CoverUpdateRequest(BaseModel):
    video_ids: list[int] = Field(default_factory=list)
    limit: int = Field(default=100, ge=1, le=2000)
    concurrent_tabs: int = Field(default=2, ge=1, le=5)
    headless: bool = True
    scope: Literal["in_scope", "out_scope", "all"] = "in_scope"


COVER_UPDATE_TASKS: dict[str, dict[str, Any]] = {}
MAX_COVER_UPDATE_TASKS = 50


def _trim_cover_update_tasks():
    if len(COVER_UPDATE_TASKS) <= MAX_COVER_UPDATE_TASKS:
        return

    sorted_items = sorted(
        COVER_UPDATE_TASKS.items(),
        key=lambda item: item[1].get("created_at") or "",
        reverse=True,
    )

    keep_ids = {task_id for task_id, _ in sorted_items[:MAX_COVER_UPDATE_TASKS]}

    for task_id in list(COVER_UPDATE_TASKS.keys()):
        if task_id not in keep_ids:
            COVER_UPDATE_TASKS.pop(task_id, None)


def _run_cover_update_background(task_id: str, params: dict[str, Any]):
    task = COVER_UPDATE_TASKS.get(task_id)

    if not task:
        return

    task["status"] = "running"
    task["started_at"] = datetime.now(timezone.utc).isoformat()
    task["logs"].append("Bắt đầu cập nhật ảnh bìa video từ TikTok.")

    def update_progress(progress: dict):
        current_task = COVER_UPDATE_TASKS.get(task_id)
        if not current_task:
            return

        current_task["progress"] = progress
        processed = progress.get("processed", 0)
        total = progress.get("total", 0)
        success = progress.get("success", 0)
        failed = progress.get("failed", 0)

        if total:
            current_task["logs"] = (
                current_task["logs"]
                + [f"Tiến độ {processed}/{total} | Thành công={success} | Thất bại={failed}"]
            )[-60:]

    try:
        from backend.services.adminVideoCoverUpdater import VideoCoverUrlUpdater

        updater = VideoCoverUrlUpdater(cookies_file=params.get("cookies_file") or "cookies.json")

        try:
            result = asyncio.run(
                updater.run(
                    limit=int(params.get("limit") or 100),
                    concurrent_tabs=int(params.get("concurrent_tabs") or 2),
                    headless=bool(params.get("headless", True)),
                    scope=params.get("scope") or "in_scope",
                    video_ids=params.get("video_ids") or None,
                    progress_callback=update_progress,
                )
            )
        finally:
            updater.close()

        task["status"] = "completed"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        task["result"] = result
        task["logs"].append(result.get("message") or "Hoàn tất cập nhật ảnh bìa video.")

    except Exception as error:
        task["status"] = "failed"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        task["error"] = str(error)
        task["logs"].append(f"Lỗi cập nhật ảnh bìa: {error}")


def _status_label(status: str | None) -> str:
    return STATUS_LABELS.get(status or "unknown", status or "Không rõ")


def _latest_stats_subquery(db: Session):
    return (
        db.query(
            VideoStat.video_id.label("video_id"),
            func.max(VideoStat.collected_at).label("latest_at"),
        )
        .group_by(VideoStat.video_id)
        .subquery()
    )


def _safe_video_ids(video_ids: list[int]) -> list[int]:
    return sorted({int(video_id) for video_id in video_ids if video_id})


def _delete_ai_and_items(db: Session, video_ids: list[int]):
    if not video_ids:
        return

    db.query(AIAnalysis).filter(AIAnalysis.video_id.in_(video_ids)).delete(
        synchronize_session=False
    )
    db.query(FashionItem).filter(FashionItem.video_id.in_(video_ids)).delete(
        synchronize_session=False
    )


def _serialize_video_row(video: Video, stat: VideoStat | None, db: Session):
    hashtag_rows = (
        db.query(Hashtag.tag_name)
        .join(video_hashtags, Hashtag.hashtag_id == video_hashtags.c.hashtag_id)
        .filter(video_hashtags.c.video_id == video.video_id)
        .order_by(Hashtag.tag_name.asc())
        .all()
    )

    item_rows = (
        db.query(
            FashionItem.item_type,
            func.max(FashionItem.confidence).label("confidence"),
            func.count(FashionItem.item_id).label("count"),
        )
        .filter(FashionItem.video_id == video.video_id)
        .group_by(FashionItem.item_type)
        .order_by(func.count(FashionItem.item_id).desc())
        .all()
    )

    return {
        "video_id": video.video_id,
        "tiktok_video_id": video.tiktok_video_id,
        "description": video.description,
        "video_url": video.video_url,
        "cover_url": video.cover_url,
        "duration_seconds": getattr(video, "duration_seconds", None),
        "created_date": getattr(video, "created_date", None),
        "collected_date": getattr(video, "collected_date", None),
        "published_at": getattr(video, "published_at", None),
        "published_text": getattr(video, "published_text", None),
        "date_confidence": getattr(video, "date_confidence", None),
        "is_in_scope": bool(getattr(video, "is_in_scope", False)),
        "exclude_reason": getattr(video, "exclude_reason", None),
        "processing_status": video.processing_status,
        "processing_status_label": _status_label(video.processing_status),
        "is_analyzed": bool(video.is_analyzed),
        "view_count": stat.view_count if stat else 0,
        "like_count": stat.like_count if stat else 0,
        "comment_count": stat.comment_count if stat else 0,
        "share_count": stat.share_count if stat else 0,
        "latest_stat_at": stat.collected_at if stat else None,
        "hashtags": [row[0] for row in hashtag_rows],
        "fashion_items": [row.item_type for row in item_rows],
        "fashion_items_detail": [
            {
                "item_type": row.item_type,
                "confidence": float(row.confidence or 0),
                "count": int(row.count or 0),
            }
            for row in item_rows
        ],
        "has_fashion_items": len(item_rows) > 0,
    }


def _build_video_query(
    db: Session,
    latest_stats,
    search: str | None,
    status: str,
    scope: str,
    analyzed: str,
    hashtag: str | None,
    item: str | None,
    published_from: str | None,
    published_to: str | None,
    min_views: int | None,
    max_views: int | None,
):
    query = (
        db.query(Video.video_id.label("video_id"))
        .outerjoin(latest_stats, latest_stats.c.video_id == Video.video_id)
        .outerjoin(
            VideoStat,
            and_(
                VideoStat.video_id == latest_stats.c.video_id,
                VideoStat.collected_at == latest_stats.c.latest_at,
            ),
        )
        .outerjoin(video_hashtags, video_hashtags.c.video_id == Video.video_id)
        .outerjoin(Hashtag, Hashtag.hashtag_id == video_hashtags.c.hashtag_id)
        .outerjoin(FashionItem, FashionItem.video_id == Video.video_id)
    )

    # Phạm vi mặc định của admin video management là video 2026/in-scope.
    if scope == "in_scope":
        query = query.filter(Video.is_in_scope == True)
    elif scope == "out_scope":
        query = query.filter(Video.is_in_scope == False)
    elif scope == "all":
        pass
    else:
        query = query.filter(Video.is_in_scope == True)

    if status != "all":
        query = query.filter(Video.processing_status == status)

    if analyzed == "true":
        query = query.filter(Video.is_analyzed == True)
    elif analyzed == "false":
        query = query.filter(Video.is_analyzed == False)

    if search:
        search_like = f"%{search.lower()}%"
        query = query.filter(
            or_(
                func.lower(Video.description).like(search_like),
                func.lower(Video.tiktok_video_id).like(search_like),
                func.lower(Video.video_url).like(search_like),
                func.lower(Hashtag.tag_name).like(search_like),
                func.lower(FashionItem.item_type).like(search_like),
            )
        )

    if hashtag:
        hashtag_like = f"%{hashtag.lower().replace('#', '').strip()}%"
        query = query.filter(func.lower(Hashtag.tag_name).like(hashtag_like))

    if item:
        query = query.filter(FashionItem.item_type == item)

    if published_from:
        try:
            date_from = datetime.strptime(published_from, "%Y-%m-%d").date()
            query = query.filter(func.date(Video.published_at) >= date_from)
        except ValueError:
            pass

    if published_to:
        try:
            date_to = datetime.strptime(published_to, "%Y-%m-%d").date()
            query = query.filter(func.date(Video.published_at) <= date_to)
        except ValueError:
            pass

    if min_views is not None:
        query = query.filter(VideoStat.view_count >= min_views)

    if max_views is not None:
        query = query.filter(VideoStat.view_count <= max_views)

    return query


# ============================================================
# Overview
# ============================================================


@router.get("/summary")
def get_admin_video_summary(
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    total_raw = db.query(func.count(Video.video_id)).scalar() or 0

    total_in_scope = (
        db.query(func.count(Video.video_id))
        .filter(Video.is_in_scope == True)
        .scalar()
        or 0
    )

    out_scope = (
        db.query(func.count(Video.video_id))
        .filter(Video.is_in_scope == False)
        .scalar()
        or 0
    )

    rows = (
        db.query(Video.processing_status, func.count(Video.video_id).label("total"))
        .filter(Video.is_in_scope == True)
        .group_by(Video.processing_status)
        .all()
    )

    status_counts = {row.processing_status or "unknown": int(row.total or 0) for row in rows}

    success = status_counts.get("success", 0)
    failed_no_fashion = status_counts.get("failed_no_fashion", 0)
    uncertain = status_counts.get("uncertain", 0)
    failed_no_frame = status_counts.get("failed_no_frame", 0) + status_counts.get("failed_no_frame_final", 0)
    error = status_counts.get("error", 0) + status_counts.get("failed", 0)
    pending = status_counts.get("pending", 0)

    processed = success + failed_no_fashion + uncertain + failed_no_frame + error
    fashion_evaluable = success + failed_no_fashion + uncertain

    avg_item_confidence = (
        db.query(func.avg(FashionItem.confidence))
        .join(Video, Video.video_id == FashionItem.video_id)
        .filter(Video.is_in_scope == True)
        .filter(Video.processing_status == "success")
        .scalar()
    )

    return {
        "total_raw": total_raw,
        "total_in_scope": total_in_scope,
        "out_scope": out_scope,
        "success": success,
        "failed_no_fashion": failed_no_fashion,
        "uncertain": uncertain,
        "failed_no_frame": failed_no_frame,
        "error": error,
        "pending": pending,
        "processed": processed,
        "pipeline_success_rate": round((success / total_in_scope) * 100, 2) if total_in_scope else 0,
        "processed_success_rate": round((success / processed) * 100, 2) if processed else 0,
        "fashion_detection_rate": round((success / fashion_evaluable) * 100, 2) if fashion_evaluable else 0,
        "technical_failure_rate": round((failed_no_frame / processed) * 100, 2) if processed else 0,
        "avg_yolo_item_confidence": round(float(avg_item_confidence or 0), 4),
        "status_counts": status_counts,
    }


# ============================================================
# List / detail
# ============================================================


@router.get("")
def list_admin_videos(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None),
    status: str = Query("all"),
    scope: Literal["in_scope", "out_scope", "all"] = Query("in_scope"),
    analyzed: Literal["all", "true", "false"] = Query("all"),
    hashtag: str | None = Query(None),
    item: str | None = Query(None),
    published_from: str | None = Query(None),
    published_to: str | None = Query(None),
    min_views: int | None = Query(None, ge=0),
    max_views: int | None = Query(None, ge=0),
    sort_by: str = Query("published_at"),
    sort_order: Literal["asc", "desc"] = Query("desc"),
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    latest_stats = _latest_stats_subquery(db)

    filtered_ids_query = _build_video_query(
        db=db,
        latest_stats=latest_stats,
        search=search,
        status=status,
        scope=scope,
        analyzed=analyzed,
        hashtag=hashtag,
        item=item,
        published_from=published_from,
        published_to=published_to,
        min_views=min_views,
        max_views=max_views,
    )

    filtered_ids_subq = filtered_ids_query.distinct().subquery()
    total = db.query(func.count()).select_from(filtered_ids_subq).scalar() or 0

    sort_map = {
        "published_at": Video.published_at,
        "collected_date": Video.collected_date,
        "views": VideoStat.view_count,
        "likes": VideoStat.like_count,
        "comments": VideoStat.comment_count,
        "shares": VideoStat.share_count,
        "status": Video.processing_status,
        "video_id": Video.video_id,
    }

    sort_col = sort_map.get(sort_by, Video.published_at)
    order_expr = sort_col.asc() if sort_order == "asc" else desc(sort_col)

    page_rows = (
        db.query(Video.video_id.label("video_id"))
        .outerjoin(latest_stats, latest_stats.c.video_id == Video.video_id)
        .outerjoin(
            VideoStat,
            and_(
                VideoStat.video_id == latest_stats.c.video_id,
                VideoStat.collected_at == latest_stats.c.latest_at,
            ),
        )
        .join(filtered_ids_subq, filtered_ids_subq.c.video_id == Video.video_id)
        .group_by(Video.video_id, sort_col)
        .order_by(order_expr.nullslast())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    video_ids = [row.video_id for row in page_rows]

    if not video_ids:
        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": ceil(total / page_size) if page_size else 1,
            "items": [],
        }

    rows = (
        db.query(Video, VideoStat)
        .outerjoin(latest_stats, latest_stats.c.video_id == Video.video_id)
        .outerjoin(
            VideoStat,
            and_(
                VideoStat.video_id == latest_stats.c.video_id,
                VideoStat.collected_at == latest_stats.c.latest_at,
            ),
        )
        .filter(Video.video_id.in_(video_ids))
        .all()
    )

    row_map = {video.video_id: (video, stat) for video, stat in rows}
    items = []

    for video_id in video_ids:
        if video_id in row_map:
            video, stat = row_map[video_id]
            items.append(_serialize_video_row(video, stat, db))

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": ceil(total / page_size) if page_size else 1,
        "items": items,
    }


@router.get("/fashion-items/options")
def get_admin_fashion_item_options(
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    rows = (
        db.query(FashionItem.item_type)
        .join(Video, Video.video_id == FashionItem.video_id)
        .filter(Video.is_in_scope == True)
        .filter(Video.processing_status == "success")
        .group_by(FashionItem.item_type)
        .order_by(FashionItem.item_type.asc())
        .all()
    )

    return [row[0] for row in rows]



@router.post("/cover-update/start")
def start_cover_update_task(
    payload: CoverUpdateRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(require_admin),
):
    video_ids = _safe_video_ids(payload.video_ids)

    task_id = str(uuid4())

    params = {
        "video_ids": video_ids,
        "limit": payload.limit,
        "concurrent_tabs": payload.concurrent_tabs,
        "headless": payload.headless,
        "scope": payload.scope,
    }

    COVER_UPDATE_TASKS[task_id] = {
        "task_id": task_id,
        "task_type": "update_video_cover_urls",
        "title": "Cập nhật ảnh bìa video",
        "status": "queued",
        "parameters": params,
        "progress": {
            "total": 0,
            "processed": 0,
            "success": 0,
            "failed": 0,
        },
        "logs": ["Đã đưa tác vụ cập nhật ảnh bìa vào hàng chờ."],
        "result": None,
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
    }

    _trim_cover_update_tasks()

    background_tasks.add_task(
        _run_cover_update_background,
        task_id,
        params,
    )

    return {
        "message": "Đã bắt đầu cập nhật ảnh bìa video.",
        "task": COVER_UPDATE_TASKS[task_id],
    }


@router.get("/cover-update/tasks/{task_id}")
def get_cover_update_task(
    task_id: str,
    current_admin=Depends(require_admin),
):
    task = COVER_UPDATE_TASKS.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ cập nhật ảnh bìa.")

    return task


@router.get("/{video_id}")
def get_admin_video_detail(
    video_id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    latest_stats = _latest_stats_subquery(db)

    row = (
        db.query(Video, VideoStat)
        .outerjoin(latest_stats, latest_stats.c.video_id == Video.video_id)
        .outerjoin(
            VideoStat,
            and_(
                VideoStat.video_id == latest_stats.c.video_id,
                VideoStat.collected_at == latest_stats.c.latest_at,
            ),
        )
        .filter(Video.video_id == video_id)
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy video")

    video, stat = row
    data = _serialize_video_row(video, stat, db)

    stat_rows = (
        db.query(VideoStat)
        .filter(VideoStat.video_id == video.video_id)
        .order_by(VideoStat.collected_at.desc())
        .limit(20)
        .all()
    )

    latest_ai = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.video_id == video.video_id)
        .order_by(desc(AIAnalysis.analysis_id))
        .first()
    )

    data["stats_history"] = [
        {
            "stat_id": row.stat_id,
            "view_count": row.view_count or 0,
            "like_count": row.like_count or 0,
            "comment_count": row.comment_count or 0,
            "share_count": row.share_count or 0,
            "collected_at": row.collected_at,
        }
        for row in stat_rows
    ]

    data["latest_ai_analysis"] = {
        "analysis_id": latest_ai.analysis_id,
        "analysis_type": latest_ai.analysis_type,
        "confidence_score": float(latest_ai.confidence_score or 0),
        "result_json": latest_ai.result_json,
        "created_at": getattr(latest_ai, "created_at", None),
    } if latest_ai else None

    return data


# ============================================================
# Actions
# ============================================================


@router.post("/bulk/reset-yolo")
def reset_videos_for_yolo(
    payload: ResetYoloRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    video_ids = _safe_video_ids(payload.video_ids)

    if not video_ids:
        raise HTTPException(status_code=400, detail="Chưa chọn video nào")

    videos = db.query(Video).filter(Video.video_id.in_(video_ids)).all()
    found_ids = [video.video_id for video in videos]

    if payload.clear_old_results:
        _delete_ai_and_items(db, found_ids)

    updated = 0
    for video in videos:
        video.processing_status = "pending"
        video.is_analyzed = False
        updated += 1

    db.commit()

    return {
        "message": f"Đã đưa {updated} video về trạng thái chờ YOLO.",
        "updated": updated,
    }


@router.post("/bulk/mark-scope")
def mark_videos_scope(
    payload: MarkScopeRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    video_ids = _safe_video_ids(payload.video_ids)

    if not video_ids:
        raise HTTPException(status_code=400, detail="Chưa chọn video nào")

    videos = db.query(Video).filter(Video.video_id.in_(video_ids)).all()

    updated = 0
    for video in videos:
        video.is_in_scope = payload.is_in_scope
        video.exclude_reason = None if payload.is_in_scope else (payload.reason or "admin_excluded")
        updated += 1

    db.commit()

    return {
        "message": "Đã cập nhật phạm vi xử lý cho video đã chọn.",
        "updated": updated,
    }


@router.patch("/{video_id}/scope")
def update_video_scope(
    video_id: int,
    payload: UpdateVideoScopeRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    video = db.query(Video).filter(Video.video_id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Không tìm thấy video")

    video.is_in_scope = payload.is_in_scope
    video.exclude_reason = None if payload.is_in_scope else (payload.reason or "admin_excluded")
    db.commit()

    return {
        "message": "Đã cập nhật phạm vi xử lý của video.",
        "video_id": video_id,
        "is_in_scope": payload.is_in_scope,
    }


@router.patch("/{video_id}/status")
def update_video_status(
    video_id: int,
    payload: UpdateVideoStatusRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    if payload.processing_status not in ALL_KNOWN_STATUSES:
        raise HTTPException(status_code=400, detail="Trạng thái xử lý không hợp lệ")

    video = db.query(Video).filter(Video.video_id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Không tìm thấy video")

    video.processing_status = payload.processing_status

    if payload.is_analyzed is not None:
        video.is_analyzed = payload.is_analyzed

    db.commit()

    return {
        "message": "Đã cập nhật trạng thái video.",
        "video_id": video_id,
        "processing_status": payload.processing_status,
    }


@router.delete("/bulk")
def delete_videos_bulk(
    payload: DeleteVideosRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    video_ids = _safe_video_ids(payload.video_ids)

    if not video_ids:
        raise HTTPException(status_code=400, detail="Chưa chọn video nào")

    if not payload.hard_delete:
        videos = db.query(Video).filter(Video.video_id.in_(video_ids)).all()
        updated = 0
        for video in videos:
            video.is_in_scope = False
            video.exclude_reason = "admin_archived"
            updated += 1
        db.commit()
        return {
            "message": f"Đã ẩn {updated} video khỏi pipeline chính.",
            "updated": updated,
            "hard_delete": False,
        }

    # Hard delete: dùng cho dữ liệu rác thật sự. Sau đó nên build lại trend_history/predictions.
    db.query(AIAnalysis).filter(AIAnalysis.video_id.in_(video_ids)).delete(synchronize_session=False)
    db.query(FashionItem).filter(FashionItem.video_id.in_(video_ids)).delete(synchronize_session=False)
    db.query(VideoStat).filter(VideoStat.video_id.in_(video_ids)).delete(synchronize_session=False)
    db.execute(video_hashtags.delete().where(video_hashtags.c.video_id.in_(video_ids)))
    deleted = db.query(Video).filter(Video.video_id.in_(video_ids)).delete(synchronize_session=False)
    db.commit()

    return {
        "message": f"Đã xóa vĩnh viễn {deleted} video.",
        "deleted": deleted,
        "hard_delete": True,
        "warning": "Sau khi xóa cứng, nên build lại trend_history và chạy lại prediction.",
    }


@router.delete("/{video_id}")
def delete_single_video(
    video_id: int,
    hard_delete: bool = Query(False),
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    payload = DeleteVideosRequest(video_ids=[video_id], hard_delete=hard_delete)
    return delete_videos_bulk(payload=payload, db=db, current_admin=current_admin)
