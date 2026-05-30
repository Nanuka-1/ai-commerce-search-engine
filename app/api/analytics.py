from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.search_analytics_service import (
    get_ai_stats,
    get_top_queries,
    get_zero_queries,
    get_intent_analytics,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/ai-stats")
def ai_stats(db: Session = Depends(get_db)):
    return get_ai_stats(db)


@router.get("/top-queries")
def top_queries(
    limit: int = 10,
    db: Session = Depends(get_db),
):
    return get_top_queries(db, limit)


@router.get("/zero-results")
def zero_results(
    limit: int = 10,
    db: Session = Depends(get_db),
):
    return get_zero_queries(db, limit)

@router.get("/intent-stats")
def intent_stats(db: Session = Depends(get_db)):
    return get_intent_analytics(db)