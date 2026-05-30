import logging
from sqlalchemy.orm import Session

from app.repositories.search_event_repository import create_search_event
from app.services.query_parser_service import normalize_search_query
from app.services.metrics_service import (
    ai_fallback_total,
    ai_used_total,
    chat_requests_total,
    search_success_total,
    search_zero_results_total,
)


logger = logging.getLogger(__name__)


def log_search_event(
    db: Session,
    user_id: str,
    query: str,
    locale: str,
    intent: str,
    items: list,
    search_context=None,
    ai_meta: dict | None = None,
):


    normalized_query = normalize_search_query(query)
    results_count = len(items)
    top_sku = None

    if items:
        first_item = items[0]

        if isinstance(first_item, dict):
            top_sku = first_item.get("sku")
        else:
            top_sku = first_item.sku
    success = results_count > 0
    ai_meta = ai_meta or {}

    search_strategy = getattr(search_context, "search_strategy", None)
    matched_by = getattr(search_context, "matched_by", None)

    chat_requests_total.inc()

    if success:
        search_success_total.inc()
    else:
        search_zero_results_total.inc()

    if ai_meta.get("ai_used"):
        ai_used_total.inc()

    if ai_meta.get("ai_fallback_used"):
        ai_fallback_total.inc()

    if success:
        search_success_total.inc()
    else:
        search_zero_results_total.inc()

    if ai_meta.get("ai_used"):
        ai_used_total.inc()

    if ai_meta.get("ai_fallback_used"):
        ai_fallback_total.inc()


    logger.info(
        "AI meta received",
        extra={
            "ai_meta": ai_meta,
            "intent": intent,
            "results_count": results_count,
            "success": success,
        },
    )

    return create_search_event(
        db=db,
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
        ai_used=ai_meta.get("ai_used", False),
        ai_mode=ai_meta.get("ai_mode"),
        ai_fallback_used=ai_meta.get("ai_fallback_used", False),
        ai_response_time_ms=ai_meta.get("ai_response_time_ms"),
        ai_error=ai_meta.get("ai_error"),
    )
