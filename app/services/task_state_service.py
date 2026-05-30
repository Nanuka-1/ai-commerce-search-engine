from app.schemas.pending_clarification import PendingClarification
from app.schemas.search_result_mode import SearchResultMode
from app.schemas.task_step import TaskStep



def resolve_current_step(result_mode: str | None) -> str:
    if result_mode == SearchResultMode.NEED_SIZE.value:
        return TaskStep.WAITING_SIZE.value

    if result_mode == SearchResultMode.BROAD_QUERY.value:
        return TaskStep.WAITING_REFINEMENT.value

    return TaskStep.COMPLETED.value

def resolve_pending_clarification(result_mode: str | None) -> str:
    if result_mode == SearchResultMode.NEED_SIZE.value:
        return PendingClarification.SIZE.value

    return PendingClarification.REFINEMENT.value

def should_create_followup_task(result_mode: str | None) -> bool:
    return result_mode in [
        SearchResultMode.NEED_SIZE.value,
        SearchResultMode.BROAD_QUERY.value,
    ]