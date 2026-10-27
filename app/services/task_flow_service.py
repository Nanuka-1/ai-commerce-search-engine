from sqlalchemy.orm import Session

from app.db.unit_of_work import single_commit
from app.services.task_state_service import (
    resolve_current_step,
    resolve_pending_clarification,
    should_create_followup_task,
)
from app.services.conversation_service import (
    create_search_task,
    update_session_context,
    update_search_task_query,
    cancel_search_task
)
from app.db.models import ConversationSession, SearchTask

from app.schemas.task_transition import TaskTransition


def create_followup_task_for_result_mode(
    db: Session,
    session: ConversationSession,
    query: str,
    result_mode: str | None,
):
    current_step = resolve_current_step(result_mode)
    pending_clarification = resolve_pending_clarification(result_mode)

    update_session_context(
        db=db,
        session=session,
        last_query=query,
        pending_clarification=pending_clarification,
    )

    return create_search_task(
        db=db,
        session=session,
        query=query,
        current_step=current_step,
    )


def sync_search_task_after_result(
    db: Session,
    session: ConversationSession,
    active_task: SearchTask | None,
    query: str,
    result_mode: str | None,
    detected_brand: str | None = None,
    detected_size: str | None = None,
    current_step: str | None = None,
    resolution_reason: str | None = None,
) -> SearchTask | None:
    # 19.10: Unit of Work — «закрыть старую + создать/обновить задачу» одним COMMIT (всё или ничего)
    with single_commit(db):
        return _sync_search_task(
            db, session, active_task, query, result_mode,
            detected_brand, detected_size, current_step, resolution_reason,
        )


def _sync_search_task(
    db: Session,
    session: ConversationSession,
    active_task: SearchTask | None,
    query: str,
    result_mode: str | None,
    detected_brand: str | None,
    detected_size: str | None,
    current_step: str | None,
    resolution_reason: str | None,
) -> SearchTask | None:
    if resolution_reason == TaskTransition.RESTART_TASK.value and active_task:
        cancel_search_task(
            db=db,
            task=active_task,
            reason="restarted_by_user",
        )
        active_task = None

    if should_create_followup_task(result_mode):
        return create_followup_task_for_result_mode(
            db=db,
            session=session,
            query=query,
            result_mode=result_mode,
        )

    if active_task:
        return update_search_task_query(
            db=db,
            task=active_task,
            query=query,
            current_step=current_step,
        )

    return create_search_task(
        db=db,
        session=session,
        query=query,
        detected_brand=detected_brand,
        detected_size=detected_size,
        current_step=current_step,
    )