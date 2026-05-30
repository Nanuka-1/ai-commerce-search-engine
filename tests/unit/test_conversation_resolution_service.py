from types import SimpleNamespace

from app.services.conversation_resolution_service import resolve_message_from_active_task
from app.schemas.task_step import TaskStep


def make_task(
    query: str,
    current_step: str = TaskStep.WAITING_REFINEMENT.value,
):
    return SimpleNamespace(
        query=query,
        current_step=current_step,
    )


def test_resolve_size_follow_up_updates_existing_query():
    task = make_task("nike women 39")

    result = resolve_message_from_active_task(task, "40")

    assert result.query == "nike women 40"
    assert result.should_search is True
    assert result.reason == "continue_task"


def test_resolve_model_size_follow_up_updates_existing_query():
    task = make_task("nike air max 39")

    result = resolve_message_from_active_task(task, "40")

    assert result.query == "nike air max 40"
    assert result.should_search is True
    assert result.reason == "continue_task"


def test_resolve_brand_change_returns_new_message():
    task = make_task("nike women 39")

    result = resolve_message_from_active_task(task, "adidas women 39")

    assert result.query == "adidas women 39"
    assert result.should_search is True
    assert result.reason == "restart_task"


def test_resolve_generic_to_model_returns_new_message():
    task = make_task("nike women 39")

    result = resolve_message_from_active_task(task, "nike air max 39")

    assert result.query == "nike air max 39"
    assert result.should_search is True
    assert result.reason == "restart_task"


def test_resolve_duplicate_query_does_not_search_again():
    task = make_task("nike women 39")

    result = resolve_message_from_active_task(task, "nike women 39")

    assert result.query == "nike women 39"
    assert result.should_search is False
    assert result.reason == "duplicate"