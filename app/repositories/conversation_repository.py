from sqlalchemy.orm import Session

from app.db.models import ConversationSession, SearchTask
from app.db.unit_of_work import save
from app.schemas.task_status import TaskStatus
from app.schemas.task_step import TaskStep

# 19.10: везде вместо `db.add(...); db.commit()` — `save(db, ...)`:
# обычно это тот же COMMIT, а внутри single_commit (task_flow_service) — flush, COMMIT один в конце.


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
def get_active_search_tasks(
    db: Session,
    session: ConversationSession,
) -> list[SearchTask]:
    return (
        db.query(SearchTask)
        .filter(SearchTask.session_id == session.id)
        .filter(SearchTask.status == TaskStatus.ACTIVE.value)
        .order_by(SearchTask.updated_at.desc())
        .all()
    )

def create_session(
    db: Session,
    user_id: str,
) -> ConversationSession:
    session = ConversationSession(
        user_id=user_id,
        status=TaskStatus.ACTIVE.value,
    )

    save(db, session)

    return session


def cancel_search_task_record(
    db: Session,
    task: SearchTask,
    reason: str = "cancelled",
) -> SearchTask:
    task.status = TaskStatus.CANCELLED.value
    task.current_step = TaskStep.COMPLETED.value
    task.completion_reason = reason

    save(db, task)

    return task

def cancel_active_search_task_records(
    db: Session,
    session: ConversationSession,
    reason: str = "replaced_by_new_task",
) -> None:
    active_tasks = get_active_search_tasks(
        db=db,
        session=session,
    )

    for task in active_tasks:
        cancel_search_task_record(
            db=db,
            task=task,
            reason=reason,
        )


def create_search_task_record(
    db: Session,
    session: ConversationSession,
    query: str,
    detected_brand: str | None = None,
    detected_size: str | None = None,
    current_step: str | None = None,
) -> SearchTask:
    cancel_active_search_task_records(
        db=db,
        session=session,
        reason="replaced_by_new_task",
    )

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

    save(db, task)

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

    save(db, task)

    return task


def complete_search_task_record(
    db: Session,
    task: SearchTask,
    reason: str = "resolved_by_search",
) -> SearchTask:
    task.status = TaskStatus.RESOLVED.value
    task.current_step = TaskStep.COMPLETED.value
    task.completion_reason = reason

    save(db, task)

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

    save(db, session)

    return session

def expire_search_task_record(
    db: Session,
    task: SearchTask,
) -> SearchTask:
    task.status = TaskStatus.EXPIRED.value

    save(db, task)

    return task