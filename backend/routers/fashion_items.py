from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import FashionItem
from backend.dependencies import get_db
from backend.security import get_current_user

router = APIRouter(prefix="/api/fashion-items", tags=["Fashion Items"])


@router.get("/top")
def get_top_fashion_items(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    rows = db.query(
        FashionItem.item_type,
        func.count(FashionItem.item_id).label("total"),
        func.avg(FashionItem.confidence).label("avg_confidence")
    ).group_by(
        FashionItem.item_type
    ).order_by(
        func.count(FashionItem.item_id).desc()
    ).limit(limit).all()

    return [
        {
            "item_type": row.item_type,
            "total": row.total,
            "avg_confidence": float(row.avg_confidence or 0)
        }
        for row in rows
    ]