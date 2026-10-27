from app.services.conversation_service import (
    get_or_create_session,
    get_active_search_task,
    cancel_search_task,
    get_active_search_tasks_for_session,
)

from app.services.task_flow_service import (
    create_followup_task_for_result_mode,
    sync_search_task_after_result,
)

from app.schemas.search_result_mode import SearchResultMode
from app.schemas.task_status import TaskStatus
from app.schemas.task_step import TaskStep
from app.schemas.task_transition import TaskTransition
from app.repositories.conversation_repository import create_search_task_record

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

def test_sync_search_task_updates_existing_task_when_search_succeeds(db):
    user_id = "test_sync_existing_task"

    session = get_or_create_session(
        db=db,
        user_id=user_id,
    )

    task = create_followup_task_for_result_mode(
        db=db,
        session=session,
        query="nike",
        result_mode=SearchResultMode.NEED_SIZE.value,
    )

    updated_task = sync_search_task_after_result(
        db=db,
        session=session,
        active_task=task,
        query="nike 44",
        result_mode=None,
        current_step=TaskStep.COMPLETED.value,
    )

    assert updated_task is not None
    assert updated_task.id == task.id
    assert updated_task.query == "nike 44"
    assert updated_task.current_step == TaskStep.COMPLETED.value

def test_cancel_search_task_marks_task_as_cancelled(db):
    user_id = "test_cancel_search_task"

    session = get_or_create_session(db=db, user_id=user_id)

    task = create_followup_task_for_result_mode(
        db=db,
        session=session,
        query="nike women 39",
        result_mode=SearchResultMode.BROAD_QUERY.value,
    )

    cancelled_task = cancel_search_task(
        db=db,
        task=task,
        reason="restarted_by_user",
    )

    assert cancelled_task.status == TaskStatus.CANCELLED.value
    assert cancelled_task.current_step == TaskStep.COMPLETED.value
    assert cancelled_task.completion_reason == "restarted_by_user"


def test_restart_task_cancels_old_task_and_creates_new_active_task(db):
    user_id = "test_restart_task_cancels_old_task"

    session = get_or_create_session(db=db, user_id=user_id)

    old_task = create_followup_task_for_result_mode(
        db=db,
        session=session,
        query="nike women 39",
        result_mode=SearchResultMode.BROAD_QUERY.value,
    )

    new_task = sync_search_task_after_result(
        db=db,
        session=session,
        active_task=old_task,
        query="adidas women 39",
        result_mode=SearchResultMode.NORMAL.value,
        detected_brand="adidas",
        detected_size="39",
        current_step=TaskStep.COMPLETED.value,
        resolution_reason=TaskTransition.RESTART_TASK.value,
    )

    assert old_task.status == TaskStatus.CANCELLED.value
    assert old_task.current_step == TaskStep.COMPLETED.value
    assert old_task.completion_reason == "restarted_by_user"

    assert new_task is not None
    assert new_task.id != old_task.id
    assert new_task.status == TaskStatus.ACTIVE.value
    assert new_task.query == "adidas women 39"
    assert new_task.detected_brand == "adidas"
    assert new_task.detected_size == "39"

    active_task = get_active_search_task(
        db=db,
        session=session,
    )

    assert active_task is not None
    assert active_task.id == new_task.id

def test_multiple_active_tasks_can_be_detected(db):
    user_id = "test_multiple_active_tasks_detected"

    session = get_or_create_session(db=db, user_id=user_id)

    create_followup_task_for_result_mode(
        db=db,
        session=session,
        query="nike women",
        result_mode=SearchResultMode.BROAD_QUERY.value,
    )

    create_followup_task_for_result_mode(
        db=db,
        session=session,
        query="adidas women",
        result_mode=SearchResultMode.BROAD_QUERY.value,
    )

    active_tasks = get_active_search_tasks_for_session(
        db=db,
        session=session,
    )

    assert len(active_tasks) == 1
    assert active_tasks[0].query == "adidas women"

def test_repository_create_search_task_record_keeps_only_one_active_task(db):
    user_id = "test_repository_single_active_task"

    session = get_or_create_session(db=db, user_id=user_id)

    create_search_task_record(
        db=db,
        session=session,
        query="nike women",
    )

    create_search_task_record(
        db=db,
        session=session,
        query="adidas women",
    )

    active_tasks = get_active_search_tasks_for_session(
        db=db,
        session=session,
    )

    assert len(active_tasks) == 1
    assert active_tasks[0].query == "adidas women"