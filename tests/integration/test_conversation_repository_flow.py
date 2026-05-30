from app.services.conversation_service import (
    get_or_create_session,
    get_active_search_task,
)

from app.services.task_flow_service import create_followup_task_for_result_mode
from app.schemas.search_result_mode import SearchResultMode
from app.schemas.task_status import TaskStatus
from app.schemas.task_step import TaskStep


def test_followup_task_is_created_and_found(db):
    user_id = "test_followup_task_found"

    session = get_or_create_session(db=db, user_id=user_id)

    task = create_followup_task_for_result_mode(
        db=db,
        session=session,
        query="nike women",
        result_mode=SearchResultMode.BROAD_QUERY.value,
    )

    assert task is not None
    assert task.status == TaskStatus.ACTIVE.value
    assert task.current_step == TaskStep.WAITING_REFINEMENT.value
    assert task.query == "nike women"

    active_task = get_active_search_task(
        db=db,
        session=session,
    )

    assert active_task is not None
    assert active_task.id == task.id
    assert active_task.query == "nike women"