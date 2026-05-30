from app.schemas.search_context import SearchContext
from app.schemas.search_request import SearchRequest
from app.schemas.task_step import TaskStep
from app.schemas.search_result_mode import SearchResultMode

def get_item_value(item, field: str):
    if isinstance(item, dict):
        return item.get(field)

    return getattr(item, field, None)


def apply_search_decision(context: SearchContext, request: SearchRequest) -> SearchContext:
    model_hint = getattr(context, "model_hint", None)

    has_model_match = False
    if model_hint:
        has_model_match = any(
            model_hint in (get_item_value(item, "name") or "").lower()
            or model_hint in (get_item_value(item, "sku") or "").lower()
            for item in context.items
        )

    # 1. Model is specified, but size is missing
    if model_hint and not request.size:
        context.result_mode = SearchResultMode.NEED_SIZE.value
        context.needs_clarification = True
        context.clarification_reason = "missing_size"

    # 2. Size is specified, but model is missing
    elif request.size and not model_hint:
        context.result_mode = SearchResultMode.NEED_MODEL.value
        context.needs_clarification = True
        context.clarification_reason = "missing_model"

    # 3. Model + size exist, and exact model was found
    elif model_hint and has_model_match:
        context.result_mode = SearchResultMode.EXACT_MODEL_MATCH.value
        context.needs_clarification = False
        context.clarification_reason = None

    # 4. Model + size exist, but exact model was not found
    elif model_hint and not has_model_match and context.total_count > 0:
        context.result_mode = SearchResultMode.FALLBACK_SIMILAR.value
        context.needs_clarification = True
        context.clarification_reason = "exact_model_not_found"

    # 5. Broad query
    elif context.total_count > 10 and not request.size and not model_hint:
        context.result_mode = SearchResultMode.BROAD_QUERY.value
        context.needs_clarification = True

        if request.category is None:
            context.clarification_reason = "missing_category"
        else:
            context.clarification_reason = "too_many_results"

    else:
        context.result_mode = SearchResultMode.NORMAL.value
        context.needs_clarification = False
        context.clarification_reason = None

    return context


def resolve_next_step(result_mode: str | None) -> str:
    if result_mode == SearchResultMode.NEED_SIZE.value:
        return TaskStep.WAITING_SIZE.value

    if result_mode == SearchResultMode.NEED_MODEL.value:
        return TaskStep.WAITING_MODEL.value

    if result_mode == SearchResultMode.BROAD_QUERY.value:
        return TaskStep.WAITING_REFINEMENT.value

    return TaskStep.COMPLETED.value