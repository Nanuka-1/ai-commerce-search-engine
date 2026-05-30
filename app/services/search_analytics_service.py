from sqlalchemy.orm import Session

from app.repositories.search_event_repository import (
    get_top_search_queries,
    get_zero_result_queries,
    get_ai_usage_stats,
    get_intent_stats,
)


def get_top_queries(db: Session, limit: int = 10) -> list[dict]:
    rows = get_top_search_queries(db=db, limit=limit)

    return [
        {
            "query": row.normalized_query,
            "count": row.search_count,
        }
        for row in rows
    ]

def get_zero_queries(db: Session, limit: int = 10) -> list[dict]:
    rows = get_zero_result_queries(db=db, limit=limit)

    return [
        {
            "query": row.normalized_query,
            "count": row.search_count,
        }
        for row in rows
    ]

def get_ai_stats(db: Session) -> dict:
    return get_ai_usage_stats(db)


def get_intent_analytics(db: Session) -> list[dict]:
    rows = get_intent_stats(db=db)

    return [
        {
            "intent": row.intent,
            "count": row.intent_count,
        }
        for row in rows
    ]

