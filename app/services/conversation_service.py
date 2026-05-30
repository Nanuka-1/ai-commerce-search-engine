from sqlalchemy.orm import Session

from app.db.models import ConversationSession, SearchTask


from app.services.intent_router import extract_size_from_query
from app.services.conversation_lifecycle_service import is_task_expired
from app.schemas.task_status import TaskStatus
from app.schemas.task_step import TaskStep
from app.schemas.pending_clarification import PendingClarification

from app.repositories.conversation_repository import (
    get_active_session_by_user_id,
    create_session,
    create_search_task_record,
    get_latest_active_search_task,
    update_search_task_record,
    complete_search_task_record,
    update_session_context_record,
    expire_search_task_record,
)


def get_or_create_session(
    db: Session,
    user_id: str,
) -> ConversationSession:

    session = get_active_session_by_user_id(db, user_id)

    if session:
        return session

    return create_session(db, user_id)

def update_session_context(
    db: Session,
    session: ConversationSession,
    last_query: str | None = None,
    last_detected_size: str | None = None,
    pending_clarification: str | None = None,
) -> ConversationSession:
    return update_session_context_record(
        db=db,
        session=session,
        last_query=last_query,
        last_detected_size=last_detected_size,
        pending_clarification=pending_clarification,
    )

def resolve_follow_up_message(
    session: ConversationSession,
    message: str,
) -> str:
    if session.pending_clarification == PendingClarification.SIZE.value:
        size = extract_size_from_query(message)

        if size and session.last_query:
            session.pending_clarification = None
            session.status = TaskStatus.COMPLETED.value

            return f"{session.last_query} {size}"

    return message

def classify_follow_up_message(message: str) -> str:
    normalized_message = message.strip().lower()

    if not normalized_message:
        return "empty"

    size = extract_size_from_query(normalized_message)
    if size:
        return "size_refinement"

    dissatisfaction_keywords = [
        "not this",
        "not suitable",
        "doesn't fit",
        "dont like",
        "don't like",
        "სხვა",
        "არ მომწონს",
    ]

    if any(keyword in normalized_message for keyword in dissatisfaction_keywords):
        return "dissatisfaction"

    category_keywords = [
        "women",
        "woman",
        "female",
        "men",
        "man",
        "male",
        "kids",
        "kid",
        "child",
        "children",
        "ქალის",
        "მამაკაცის",
        "ბავშვის",
    ]

    if any(keyword in normalized_message for keyword in category_keywords):
        return "category_refinement"

    product_refinement_keywords = [
        "white",
        "black",
        "red",
        "blue",
        "running",
        "football",
        "basketball",
        "casual",
        "training",
        "თეთრი",
        "შავი",
    ]

    if any(keyword in normalized_message for keyword in product_refinement_keywords):
        return "product_refinement"

    return "general_refinement"


def create_search_task(
    db: Session,
    session: ConversationSession,
    query: str,
    detected_brand: str | None = None,
    detected_size: str | None = None,
    current_step: TaskStep | str | None = None,
) -> SearchTask:
    return create_search_task_record(
        db=db,
        session=session,
        query=query,
        detected_brand=detected_brand,
        detected_size=detected_size,
        current_step=current_step,
    )

def get_active_search_task(
    db: Session,
    session: ConversationSession,
    timeout_minutes: int = 15,
) -> SearchTask | None:
    task = get_latest_active_search_task(db, session)

    if task is None:
        return None

    if is_task_expired(task, timeout_minutes=timeout_minutes):
        expire_search_task_record(db, task)
        return None

    return task



def update_search_task_query(
    db: Session,
    task: SearchTask,
    query: str,
    current_step: TaskStep | str | None = None,
) -> SearchTask:
    return update_search_task_record(
        db=db,
        task=task,
        query=query,
        current_step=current_step,
    )



def complete_search_task(
    db: Session,
    task: SearchTask,
    reason: str = "resolved_by_search",
) -> SearchTask:
    return complete_search_task_record(
        db=db,
        task=task,
        reason=reason,
    )



