from app.schemas.pending_clarification import PendingClarification
from app.schemas.search_result_mode import SearchResultMode
from app.schemas.task_step import TaskStep
from app.services.task_state_service import (
    resolve_current_step,
    resolve_pending_clarification,
    should_create_followup_task,
)


def test_resolve_current_step_need_size():
    assert (
        resolve_current_step(SearchResultMode.NEED_SIZE.value)
        == TaskStep.WAITING_SIZE.value
    )


def test_resolve_current_step_broad_query():
    assert (
        resolve_current_step(SearchResultMode.BROAD_QUERY.value)
        == TaskStep.WAITING_REFINEMENT.value
    )


def test_resolve_current_step_default_completed():
    assert resolve_current_step(SearchResultMode.NORMAL.value) == TaskStep.COMPLETED.value


def test_resolve_pending_clarification_need_size():
    assert (
        resolve_pending_clarification(SearchResultMode.NEED_SIZE.value)
        == PendingClarification.SIZE.value
    )


def test_resolve_pending_clarification_default_refinement():
    assert (
        resolve_pending_clarification(SearchResultMode.BROAD_QUERY.value)
        == PendingClarification.REFINEMENT.value
    )


def test_should_create_followup_task_for_need_size():
    assert should_create_followup_task(SearchResultMode.NEED_SIZE.value) is True


def test_should_create_followup_task_for_broad_query():
    assert should_create_followup_task(SearchResultMode.BROAD_QUERY.value) is True


def test_should_not_create_followup_task_for_normal():
    assert should_create_followup_task(SearchResultMode.NORMAL.value) is False