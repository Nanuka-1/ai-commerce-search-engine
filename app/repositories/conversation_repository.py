from sqlalchemy.orm import Session

from app.db.models import ConversationSession, SearchTask
from app.schemas.task_status import TaskStatus
from app.schemas.task_step import TaskStep



def get_active_session_by_user_id(
    db: Session,
    user_id: str,
) -> ConversationSession | None:
    return (
        db.query(ConversationSession)
        .filter(ConversationSession.user_id == user_id)
        .filter(ConversationSession.status == TaskStatus.ACTIVE.value)
        .first()
    )

def create_session(
    db: Session,
    user_id: str,
) -> ConversationSession:
    session = ConversationSession(
        user_id=user_id,
        status=TaskStatus.ACTIVE.value,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session

def create_search_task_record(
    db: Session,
    session: ConversationSession,
    query: str,
    detected_brand: str | None = None,
    detected_size: str | None = None,
    current_step: str | None = None,
) -> SearchTask:
    task = SearchTask(
        session_id=session.id,
        query=query,
        detected_brand=detected_brand,
        detected_size=detected_size,
        current_step=(
            current_step.value
            if isinstance(current_step, TaskStep)
            else current_step
        ),
        status=TaskStatus.ACTIVE.value,
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task

def get_latest_active_search_task(
    db: Session,
    session: ConversationSession,
) -> SearchTask | None:
    return (
        db.query(SearchTask)
        .filter(SearchTask.session_id == session.id)
        .filter(SearchTask.status == TaskStatus.ACTIVE.value)
        .order_by(SearchTask.updated_at.desc())
        .first()
    )

def update_search_task_record(
    db: Session,
    task: SearchTask,
    query: str,
    current_step: TaskStep | str | None = None,
) -> SearchTask:
    task.query = query

    if current_step:
        task.current_step = (
            current_step.value
            if isinstance(current_step, TaskStep)
            else current_step
        )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task


def complete_search_task_record(
    db: Session,
    task: SearchTask,
    reason: str = "resolved_by_search",
) -> SearchTask:
    task.status = TaskStatus.RESOLVED.value
    task.current_step = TaskStep.COMPLETED.value
    task.completion_reason = reason

    db.add(task)
    db.commit()
    db.refresh(task)

    return task


def update_session_context_record(
    db: Session,
    session: ConversationSession,
    last_query: str | None = None,
    last_detected_size: str | None = None,
    pending_clarification: str | None = None,
) -> ConversationSession:
    session.last_query = last_query
    session.last_detected_size = last_detected_size
    session.pending_clarification = pending_clarification

    db.add(session)
    db.commit()
    db.refresh(session)

    return session

def expire_search_task_record(
    db: Session,
    task: SearchTask,
) -> SearchTask:
    task.status = TaskStatus.EXPIRED.value

    db.add(task)
    db.commit()
    db.refresh(task)

    return task