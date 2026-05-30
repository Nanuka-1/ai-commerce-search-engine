from sqlalchemy.orm import Session

from app.db.models import ConversationSession

from app.services.conversation_service import (
    create_search_task,
    update_session_context,
)
from app.services.task_state_service import (
    resolve_current_step,
    resolve_pending_clarification,
)


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