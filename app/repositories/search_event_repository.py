from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.db.models import SearchEvent


def create_search_event(
    db: Session,
    user_id: str,
    query: str,
    normalized_query: str,
    locale: str,
    intent: str,
    search_strategy: str | None,
    matched_by: str | None,
    results_count: int,
    top_sku: str | None,
    success: bool,
    ai_used: bool = False,
    ai_mode: str | None = None,
    ai_fallback_used: bool = False,
    ai_response_time_ms: float | None = None,
    ai_error: str | None = None,
) -> SearchEvent:
    event = SearchEvent(
        user_id=user_id,
        query=query,
        normalized_query=normalized_query,
        locale=locale,
        intent=intent,
        search_strategy=search_strategy,
        matched_by=matched_by,
        results_count=results_count,
        top_sku=top_sku,
        success=success,
        ai_used=ai_used,
        ai_mode=ai_mode,
        ai_fallback_used=ai_fallback_used,
        ai_response_time_ms=ai_response_time_ms,
        ai_error=ai_error,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_top_search_queries(
    db: Session,
    limit: int = 10,
):
    return (
        db.query(
            SearchEvent.normalized_query,
            func.count(SearchEvent.id).label("search_count"),
        )
        .filter(SearchEvent.success.is_(True))
        .group_by(SearchEvent.normalized_query)
        .order_by(desc("search_count"))
        .limit(limit)
        .all()
    )


def get_zero_result_queries(
    db: Session,
    limit: int = 10,
):
    return (
        db.query(
            SearchEvent.normalized_query,
            func.count(SearchEvent.id).label("search_count"),
        )
        .filter(SearchEvent.success.is_(False))
        .group_by(SearchEvent.normalized_query)
        .order_by(desc("search_count"))
        .limit(limit)
        .all()
    )

def get_ai_usage_stats(db: Session):
    total_events = db.query(func.count(SearchEvent.id)).scalar()

    ai_used_events = (
        db.query(func.count(SearchEvent.id))
        .filter(SearchEvent.ai_used.is_(True))
        .scalar()
    )

    ai_fallback_events = (
        db.query(func.count(SearchEvent.id))
        .filter(SearchEvent.ai_fallback_used.is_(True))
        .scalar()
    )

    return {
        "total_events": total_events,
        "ai_used_events": ai_used_events,
        "ai_fallback_events": ai_fallback_events,
    }

def get_intent_stats(db: Session):
    return (
        db.query(
            SearchEvent.intent,
            func.count(SearchEvent.id).label("intent_count"),
        )
        .group_by(SearchEvent.intent)
        .order_by(desc("intent_count"))
        .all()
    )