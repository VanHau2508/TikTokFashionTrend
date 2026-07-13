from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from database.models import Hashtag, TrendHistory, Prediction
from backend.dependencies import get_db
from backend.security import get_current_user
from ai.tag_filters import BLACKLIST_TAGS

router = APIRouter(prefix="/api/trends", tags=["Trends"])

LSTM_V3_MODEL_VERSION = "lstm_trend_history_growth_v3"


def serialize_trend_row(row):
    return {
        "hashtag_id": row.hashtag_id,
        "tag_name": row.tag_name,
        "date": row.date,
        "view_count": row.view_count or 0,
        "like_count": row.like_count or 0,
        "comment_count": row.comment_count or 0,
        "share_count": row.share_count or 0,
        "video_count": row.video_count or 0,
        "engagement_rate": row.engagement_rate or 0,
        "view_growth": row.view_growth or 0,
        "like_growth": row.like_growth or 0,
        "engagement_growth": row.engagement_growth or 0,
        "trend_score": row.trend_score or 0,
        "trending_score": row.trend_score or 0,
    }


@router.get("/top")
def get_top_trends(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    latest_date = db.query(func.max(TrendHistory.date)).scalar()

    if not latest_date:
        return []

    rows = (
        db.query(
            Hashtag.hashtag_id,
            Hashtag.tag_name,
            TrendHistory.date,
            TrendHistory.view_count,
            TrendHistory.like_count,
            TrendHistory.comment_count,
            TrendHistory.share_count,
            TrendHistory.video_count,
            TrendHistory.engagement_rate,
            TrendHistory.view_growth,
            TrendHistory.like_growth,
            TrendHistory.engagement_growth,
            TrendHistory.trend_score,
        )
        .join(TrendHistory, TrendHistory.hashtag_id == Hashtag.hashtag_id)
        .filter(TrendHistory.date == latest_date)
        .filter(~func.lower(Hashtag.tag_name).in_(list(BLACKLIST_TAGS)))
        .order_by(TrendHistory.view_count.desc())
        .limit(limit)
        .all()
    )

    return [serialize_trend_row(row) for row in rows]


@router.get("/emerging")
def get_emerging_trends(
    limit: int = Query(20, ge=1, le=100),
    min_video_count: int = Query(5, ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    latest_date = db.query(func.max(TrendHistory.date)).scalar()

    if not latest_date:
        return []

    rows = (
        db.query(
            Hashtag.hashtag_id,
            Hashtag.tag_name,
            TrendHistory.date,
            TrendHistory.view_count,
            TrendHistory.like_count,
            TrendHistory.comment_count,
            TrendHistory.share_count,
            TrendHistory.video_count,
            TrendHistory.engagement_rate,
            TrendHistory.view_growth,
            TrendHistory.like_growth,
            TrendHistory.engagement_growth,
            TrendHistory.trend_score,
        )
        .join(TrendHistory, TrendHistory.hashtag_id == Hashtag.hashtag_id)
        .filter(TrendHistory.date == latest_date)
        .filter(TrendHistory.video_count >= min_video_count)
        .filter(TrendHistory.view_growth > 0)
        .filter(~func.lower(Hashtag.tag_name).in_(list(BLACKLIST_TAGS)))
        .order_by(TrendHistory.view_growth.desc())
        .limit(limit)
        .all()
    )

    return [serialize_trend_row(row) for row in rows]


@router.get("/predictions")
def get_predicted_trends(
    limit: int = Query(20, ge=1, le=100),
    model_version: str = Query(LSTM_V3_MODEL_VERSION),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    latest_prediction_date = (
        db.query(func.max(Prediction.prediction_date))
        .filter(Prediction.model_version == model_version)
        .filter(Prediction.prediction_type == "view_growth")
        .scalar()
    )

    if not latest_prediction_date:
        return []

    rows = (
        db.query(
            Prediction.prediction_id,
            Prediction.hashtag_id,
            Hashtag.tag_name,
            Prediction.prediction_date,
            Prediction.predicted_for_date,
            Prediction.predicted_value,
            Prediction.model_version,
            TrendHistory.view_count.label("latest_view_count"),
            TrendHistory.video_count.label("video_count"),
        )
        .join(Hashtag, Hashtag.hashtag_id == Prediction.hashtag_id)
        .outerjoin(
            TrendHistory,
            (TrendHistory.hashtag_id == Prediction.hashtag_id)
            & (TrendHistory.date == Prediction.prediction_date),
        )
        .filter(Prediction.model_version == model_version)
        .filter(Prediction.prediction_type == "view_growth")
        .filter(Prediction.prediction_date == latest_prediction_date)
        .filter(Prediction.predicted_value.isnot(None))
        .filter(~func.lower(Hashtag.tag_name).in_(list(BLACKLIST_TAGS)))
        .order_by(desc(Prediction.predicted_value))
        .limit(limit)
        .all()
    )

    return [
        {
            "prediction_id": row.prediction_id,
            "hashtag_id": row.hashtag_id,
            "tag_name": row.tag_name,
            "prediction_date": row.prediction_date,
            "predicted_for_date": row.predicted_for_date,
            "predicted_growth": float(row.predicted_value or 0),
            "predicted_value": float(row.predicted_value or 0),
            "predicted_next_views": float(row.latest_view_count or 0)
            + float(row.predicted_value or 0),
            "video_count": row.video_count or 0,
            "model_version": row.model_version,
        }
        for row in rows
    ]


@router.get("/predicted")
def get_predicted_trends_alias(
    limit: int = Query(20, ge=1, le=100),
    model_version: str = Query(LSTM_V3_MODEL_VERSION),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return get_predicted_trends(
        limit=limit,
        model_version=model_version,
        db=db,
        current_user=current_user,
    )


@router.get("/predicted-trends")
def get_predicted_trends_alias_2(
    limit: int = Query(20, ge=1, le=100),
    model_version: str = Query(LSTM_V3_MODEL_VERSION),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return get_predicted_trends(
        limit=limit,
        model_version=model_version,
        db=db,
        current_user=current_user,
    )


@router.get("/history/{hashtag_id}")
def get_trend_history(
    hashtag_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    hashtag = db.query(Hashtag).filter(Hashtag.hashtag_id == hashtag_id).first()

    if not hashtag:
        return {
            "hashtag_id": hashtag_id,
            "tag_name": None,
            "history": [],
        }

    rows = (
        db.query(TrendHistory)
        .filter(TrendHistory.hashtag_id == hashtag_id)
        .order_by(TrendHistory.date.asc())
        .all()
    )

    return {
        "hashtag_id": hashtag.hashtag_id,
        "tag_name": hashtag.tag_name,
        "history": [
            {
                "date": row.date,
                "view_count": row.view_count or 0,
                "like_count": row.like_count or 0,
                "comment_count": row.comment_count or 0,
                "share_count": row.share_count or 0,
                "video_count": row.video_count or 0,
                "engagement_rate": row.engagement_rate or 0,
                "view_growth": row.view_growth or 0,
                "like_growth": row.like_growth or 0,
                "engagement_growth": row.engagement_growth or 0,
                "trend_score": row.trend_score or 0,
                "trending_score": row.trend_score or 0,
                "is_imputed": bool(getattr(row, "is_imputed", False)),
                "data_quality_score": getattr(row, "data_quality_score", 1.0) or 1.0,
            }
            for row in rows
        ],
    }