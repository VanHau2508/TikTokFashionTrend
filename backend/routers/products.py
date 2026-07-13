from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func, or_, desc, and_
from sqlalchemy.orm import Session

from database.models import Video, VideoStat, Hashtag, FashionItem, video_hashtags
from backend.dependencies import get_db
from backend.security import get_current_user

from math import ceil

router = APIRouter(prefix="/api/products", tags=["Products"])


PRODUCT_CATEGORIES = {
    "men": {
        "label": "Thời Trang Nam",
        "description": "Video có dấu hiệu liên quan đến outfit nam, menswear, men style.",
        "keywords": [
            "phoidonam",
            "thời trang nam",
            "thoitrangnam",
            "outfitnam",
            "menfashion",
            "menoutfit",
            "menswear",
            "mensstyle",
            "men style",
            "nam",
            "boy outfit",
            "polo nam",
            "style nam",
        ],
        "items": [],
    },
    "women": {
        "label": "Thời Trang Nữ",
        "description": "Video có dấu hiệu liên quan đến outfit nữ, women fashion, váy, đầm.",
        "keywords": [
            "phoidonu",
            "thời trang nữ",
            "thoitrangnu",
            "outfitnu",
            "womenfashion",
            "womenoutfit",
            "womenswear",
            "girl outfit",
            "fashiongirl",
            "nữ",
            "váy",
            "đầm",
            "crop top",
            "style nữ",
        ],
        "items": [],
    },
    "accessories": {
        "label": "Phụ Kiện & Giày Dép",
        "description": "Video có item phụ kiện hoặc giày dép được YOLO phát hiện.",
        "keywords": [
            "phukien",
            "phụ kiện",
            "accessory",
            "accessories",
            "bag",
            "hat",
            "cap",
            "glasses",
            "watch",
            "shoes",
            "sneaker",
        ],
        "items": [
            "bags",
            "backpack",
            "watch",
            "cap",
            "sunglasses",
            "sneakers",
            "formal_shoes",
            "slippers",
            "sandals",
        ],
    },
}

STYLE_FILTERS = {
    "all": [],
    "streetwear": [
        "streetwear", "skate", "skater", "baggy", "oversize", "hoodie",
        "cargo", "sneaker", "hiphop"
    ],
    "y2k": [
        "y2k", "vintage", "retro", "affliction", "jnco", "2000s",
        "grunge"
    ],
    "basic": [
        "basic", "simple", "minimal", "daily", "casual"
    ],
    "formal": [
        "formal", "office", "oldmoney", "old money", "polo", "blazer", "shirt"
    ],
    "sporty": [
        "sport", "gym", "athletic", "sneaker", "shorts"
    ],
}


def get_latest_stats_subquery(db: Session):
    return (
        db.query(
            VideoStat.video_id.label("video_id"),
            func.max(VideoStat.collected_at).label("latest_collected_at")
        )
        .group_by(VideoStat.video_id)
        .subquery()
    )


def calculate_video_growth(video_id: int, latest_collected_at, latest_view_count: int, db: Session):
    previous_stat = (
        db.query(VideoStat)
        .filter(
            VideoStat.video_id == video_id,
            VideoStat.collected_at < latest_collected_at,
        )
        .order_by(VideoStat.collected_at.desc())
        .first()
    )

    if not previous_stat:
        return 0

    return max(0, int(latest_view_count or 0) - int(previous_stat.view_count or 0))


def collect_product_videos(
    db: Session,
    category: str,
    style: str = "all",
    search: str | None = None,
    sort_by: str = "views"
):
    config = PRODUCT_CATEGORIES.get(category)

    if not config:
        return []

    latest_stat_subquery = get_latest_stats_subquery(db)

    category_conditions = []

    for keyword in config["keywords"]:
        keyword_like = f"%{keyword.lower()}%"
        category_conditions.append(func.lower(Video.description).like(keyword_like))
        category_conditions.append(func.lower(Hashtag.tag_name).like(keyword_like))

    for item in config["items"]:
        item_like = f"%{item.lower()}%"
        category_conditions.append(func.lower(FashionItem.item_type).like(item_like))

    query = (
        db.query(
            Video.video_id,
            Video.tiktok_video_id,
            Video.description,
            Video.video_url,
            Video.cover_url,
            Video.processing_status,
            Video.is_analyzed,
            VideoStat.view_count,
            VideoStat.like_count,
            VideoStat.comment_count,
            VideoStat.share_count,
            VideoStat.collected_at,
            Hashtag.tag_name,
            FashionItem.item_type,
        )
        .join(
            latest_stat_subquery,
            latest_stat_subquery.c.video_id == Video.video_id
        )
        .join(
            VideoStat,
            and_(
                VideoStat.video_id == latest_stat_subquery.c.video_id,
                VideoStat.collected_at == latest_stat_subquery.c.latest_collected_at
            )
        )
        .outerjoin(video_hashtags, video_hashtags.c.video_id == Video.video_id)
        .outerjoin(Hashtag, Hashtag.hashtag_id == video_hashtags.c.hashtag_id)
        .outerjoin(FashionItem, FashionItem.video_id == Video.video_id)
        .filter(Video.is_in_scope == True)
        .filter(Video.processing_status == "success")
        .filter(Video.is_analyzed == True)
    )

    if category_conditions:
        query = query.filter(or_(*category_conditions))

    style_keywords = STYLE_FILTERS.get(style, [])

    if style != "all" and style_keywords:
        style_conditions = []

        for keyword in style_keywords:
            keyword_like = f"%{keyword.lower()}%"
            style_conditions.append(func.lower(Video.description).like(keyword_like))
            style_conditions.append(func.lower(Hashtag.tag_name).like(keyword_like))
            style_conditions.append(func.lower(FashionItem.item_type).like(keyword_like))

        query = query.filter(or_(*style_conditions))

    if search:
        search_like = f"%{search.lower()}%"
        query = query.filter(
            or_(
                func.lower(Video.description).like(search_like),
                func.lower(Hashtag.tag_name).like(search_like),
                func.lower(FashionItem.item_type).like(search_like)
            )
        )

    rows = query.all()

    video_map = {}

    for row in rows:
        if row.video_id not in video_map:
            view_growth = calculate_video_growth(
                row.video_id,
                row.collected_at,
                row.view_count,
                db
            )

            video_map[row.video_id] = {
                "video_id": row.video_id,
                "tiktok_video_id": row.tiktok_video_id,
                "description": row.description,
                "video_url": row.video_url,
                "cover_url": row.cover_url,
                "processing_status": row.processing_status,
                "is_analyzed": row.is_analyzed,
                "view_count": row.view_count or 0,
                "like_count": row.like_count or 0,
                "comment_count": row.comment_count or 0,
                "share_count": row.share_count or 0,
                "view_growth": view_growth,
                "trend_score": view_growth or row.view_count or 0,
                "collected_at": row.collected_at,
                "hashtags": set(),
                "fashion_items": set(),
                "has_yolo_result": True,
            }

        if row.tag_name:
            video_map[row.video_id]["hashtags"].add(row.tag_name)

        if row.item_type:
            video_map[row.video_id]["fashion_items"].add(row.item_type)

    result = []

    for item in video_map.values():
        item["hashtags"] = list(item["hashtags"])
        item["fashion_items"] = list(item["fashion_items"])
        item["has_fashion_items"] = len(item["fashion_items"]) > 0
        result.append(item)

    if sort_by == "likes":
        result.sort(key=lambda item: item.get("like_count") or 0, reverse=True)
    elif sort_by == "comments":
        result.sort(key=lambda item: item.get("comment_count") or 0, reverse=True)
    elif sort_by == "shares":
        result.sort(key=lambda item: item.get("share_count") or 0, reverse=True)
    elif sort_by == "growth":
        result.sort(key=lambda item: item.get("view_growth") or 0, reverse=True)
    else:
        result.sort(key=lambda item: item.get("view_count") or 0, reverse=True)

    return result


@router.get("/categories")
def get_product_categories(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = []

    for key, config in PRODUCT_CATEGORIES.items():
        videos = collect_product_videos(
            db=db,
            category=key,
            style="all",
            search=None,
            sort_by="views"
        )

        result.append({
            "category": key,
            "label": config["label"],
            "description": config["description"],
            "video_count": len(videos),
            "top_views": sum([video["view_count"] or 0 for video in videos]),
            "success_only": True,
            "scope": "in_scope_2026",
        })

    return result


@router.get("/{category}/videos")
def get_product_category_videos(
    category: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    style: str = Query("all"),
    search: str | None = Query(None),
    sort_by: str = Query("views"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    config = PRODUCT_CATEGORIES.get(category)

    if not config:
        raise HTTPException(
            status_code=404,
            detail="Danh mục sản phẩm không tồn tại"
        )

    all_items = collect_product_videos(
        db=db,
        category=category,
        style=style,
        search=search,
        sort_by=sort_by
    )

    total = len(all_items)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_items = all_items[start:end]

    return {
        "category": category,
        "label": config["label"],
        "description": config["description"],
        "style": style,
        "search": search,
        "sort_by": sort_by,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": ceil(total / page_size) if page_size else 1,
        "items": paginated_items,
        "success_only": True,
        "scope": "in_scope_2026",
    }
