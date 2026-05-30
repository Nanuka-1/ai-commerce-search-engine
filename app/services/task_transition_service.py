from app.db.models import SearchTask

from app.schemas.task_transition import TaskTransition

from app.services.search_constraints_service import (
    extract_constraints_from_message,
)
from app.services.query_parser_service import (
    extract_model_hint_from_query,
)


def is_new_model_search(
    message_model_hint: str | None,
    task_model_hint: str | None,
) -> bool:
    return bool(message_model_hint and message_model_hint != task_model_hint)


def is_model_replacement(
    task_model_hint: str | None,
    message_brand: str | None,
    message_size: str | None,
    new_tokens: set[str],
) -> bool:
    return bool(task_model_hint and message_brand and message_size and new_tokens)


def is_model_size_refinement(
    task_model_hint: str | None,
    message_size: str | None,
    message_model_hint: str | None,
) -> bool:
    return bool(task_model_hint and message_size and not message_model_hint)


def is_size_only_refinement(
    message_size: str | None,
    message_brand: str | None,
    message_model_hint: str | None,
) -> bool:
    return bool(message_size and not message_brand and not message_model_hint)


def is_duplicate_query(new_tokens: set[str]) -> bool:
    return not new_tokens


def is_brand_switch(
    message_brand: str | None,
    task_brand: str | None,
) -> bool:
    return bool(message_brand and task_brand and message_brand != task_brand)


def is_brand_introduced(
    message_brand: str | None,
    task_brand: str | None,
) -> bool:
    return bool(message_brand and not task_brand)


def classify_task_transition(task: SearchTask | None, message: str) -> str:
    if task is None or not task.query:
        return TaskTransition.NEW_TASK.value

    normalized_message = message.strip().lower()
    normalized_task_query = task.query.strip().lower()

    if not normalized_message:
        return TaskTransition.CONTINUE_TASK.value

    message_constraints = extract_constraints_from_message(normalized_message)
    task_constraints = extract_constraints_from_message(normalized_task_query)

    message_brand = message_constraints.brand
    task_brand = task_constraints.brand

    message_size = message_constraints.size

    message_model_hint = extract_model_hint_from_query(normalized_message)
    task_model_hint = extract_model_hint_from_query(normalized_task_query)

    message_tokens = set(normalized_message.split())
    task_tokens = set(normalized_task_query.split())
    new_tokens = message_tokens - task_tokens

    if is_new_model_search(message_model_hint, task_model_hint):
        return TaskTransition.RESTART_TASK.value

    if is_brand_switch(message_brand, task_brand):
        return TaskTransition.RESTART_TASK.value

    if is_brand_introduced(message_brand, task_brand):
        return TaskTransition.RESTART_TASK.value

    if is_model_replacement(
        task_model_hint=task_model_hint,
        message_brand=message_brand,
        message_size=message_size,
        new_tokens=new_tokens,
    ):
        return TaskTransition.RESTART_TASK.value

    if is_model_size_refinement(
        task_model_hint=task_model_hint,
        message_size=message_size,
        message_model_hint=message_model_hint,
    ):
        return TaskTransition.CONTINUE_TASK.value

    if is_size_only_refinement(
        message_size=message_size,
        message_brand=message_brand,
        message_model_hint=message_model_hint,
    ):
        return TaskTransition.CONTINUE_TASK.value

    if is_duplicate_query(new_tokens):
        return TaskTransition.IGNORE_DUPLICATE.value

    return TaskTransition.CONTINUE_TASK.value
