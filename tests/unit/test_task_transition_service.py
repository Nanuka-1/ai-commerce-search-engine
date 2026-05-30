from types import SimpleNamespace

from app.services.task_transition_service import classify_task_transition
from app.schemas.task_step import TaskStep
from app.schemas.task_transition import TaskTransition


def make_task(
    query: str,
    current_step: str = TaskStep.WAITING_REFINEMENT.value,
):
    return SimpleNamespace(
        query=query,
        current_step=current_step,
    )


def test_size_update_continues_task():
    task = make_task("nike women 39")

    result = classify_task_transition(task, "40")

    assert result == TaskTransition.CONTINUE_TASK.value


def test_model_size_update_continues_task():
    task = make_task("nike air max 39")

    result = classify_task_transition(task, "40")

    assert result == TaskTransition.CONTINUE_TASK.value


def test_brand_change_restarts_task():
    task = make_task("nike women 39")

    result = classify_task_transition(task, "adidas women 39")

    assert result == TaskTransition.RESTART_TASK.value


def test_generic_search_to_model_search_restarts_task():
    task = make_task("nike women 39")

    result = classify_task_transition(task, "nike air max 39")

    assert result == TaskTransition.RESTART_TASK.value


def test_model_change_restarts_task():
    task = make_task("nike air max 39")

    result = classify_task_transition(task, "nike revolution 39")

    assert result == TaskTransition.RESTART_TASK.value


def test_duplicate_query_is_ignored():
    task = make_task("nike women 39")

    result = classify_task_transition(task, "nike women 39")

    assert result == TaskTransition.IGNORE_DUPLICATE.value