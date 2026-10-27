from types import SimpleNamespace

import pytest

from app.schemas.task_transition import TaskTransition
from app.services.conversation_resolution_service import refine_task_query, resolve_message_from_active_task
from app.services.intent_router import is_sku
from app.services.task_transition_service import classify_task_transition


def _task(query):
    return SimpleNamespace(query=query)


# --- 09.10: живой тест — прошлый запрос "прилипал" к новому ---
@pytest.mark.parametrize("task_query, message", [
    ("nkie pegasos 42", "ქალის ზამთრის ქურთუკი M"),      # свой товар → новый поиск (было: pegasus + M)
    ("nkie pegasos 42", "CW2288-111"),                  # артикул → новый поиск
    ("nike 42", "rogor xar"),                           # латиница/болтовня → не склеивать с nike
    ("სარბენი ფეხსაცმელი 42", "ზამთრის ქურთუკი"),
])
def test_message_with_own_product_words_restarts(task_query, message):
    assert classify_task_transition(_task(task_query), message) == TaskTransition.RESTART_TASK.value


@pytest.mark.parametrize("task_query, message", [
    ("nike pegasus 42", "43"),
    ("nike pegasus 42", "ზომა 43"),
    ("სარბენი ფეხსაცმელი 42", "შავი"),
    ("სარბენი ფეხსაცმელი 42", "ქალის"),
])
def test_pure_refinement_continues(task_query, message):
    assert classify_task_transition(_task(task_query), message) == TaskTransition.CONTINUE_TASK.value


@pytest.mark.parametrize("task_query, message, expected", [
    ("nike pegasus 42", "43", "nike pegasus 43"),
    ("სარბენი ფეხსაცმელი 42", "43", "სარბენი ფეხსაცმელი 43"),          # раньше оставалось только "43"
    ("სარბენი ფეხსაცმელი 42", "შავი", "სარბენი ფეხსაცმელი 42 შავი"),
])
def test_refinement_keeps_original_words(task_query, message, expected):
    assert refine_task_query(task_query, message) == expected


def test_resolution_uses_new_message_after_restart():
    resolution = resolve_message_from_active_task(_task("nkie pegasos 42"), "ქალის ზამთრის ქურთუკი M")
    assert resolution.query == "ქალის ზამთრის ქურთუკი M" and resolution.reason == "restart_task"


@pytest.mark.parametrize("text, expected", [
    ("33", False), ("42", False), ("42.5", False), ("2XL", False),   # размеры — не артикул
    ("31241503", True), ("CW2288-111", True), ("FD2722-002-44", True),
])
def test_short_numbers_are_not_sku(text, expected):
    assert is_sku(text) is expected