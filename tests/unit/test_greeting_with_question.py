"""22.10 (шаг 2а): «გამარჯობათ + вопрос» — отвечаем на вопрос, а не только приветствием.
Живьём 21.10: «გამარჯობათ ახალი კოლექციიდან ფეხსაცმელი მაინტერესებს 36 ზომა» → только «გამარჯობა! რით…» (дважды)."""
from types import SimpleNamespace

import pytest

import app.use_cases.chat_use_case as chat_module
from app.services import cache_service
from app.services.intent_router import is_greeting, strip_greeting
from app.use_cases.chat_use_case import ChatUseCase


@pytest.mark.parametrize("message", ["გამარჯობა", "გამარჯობათ!", "hello there", "დილა მშვიდობისა 👋", "Hi!"])
def test_pure_greeting_is_greeting(message):
    assert is_greeting(message) is True


@pytest.mark.parametrize("message", [
    "გამარჯობათ ახალი კოლექციიდან ფეხსაცმელი მაინტერესებს 36 ზომა",
    "გამარჯობა, ქალის ქურთუკი M",
    "hello, nike 42",
])
def test_greeting_with_question_is_not_greeting(message):
    assert is_greeting(message) is False


@pytest.mark.parametrize("message, rest", [
    ("გამარჯობათ ახალი კოლექციიდან ფეხსაცმელი 36", "ახალი კოლექციიდან ფეხსაცმელი 36"),
    ("გამარჯობა, ქალის ქურთუკი M", "ქალის ქურთუკი M"),
    ("დილა მშვიდობისა! nike 42", "nike 42"),
    ("ქალის ქურთუკი M", "ქალის ქურთუკი M"),       # без приветствия — без изменений
    ("გამარჯობა!", ""),                           # только приветствие — остатка нет
])
def test_strip_greeting(message, rest):
    assert strip_greeting(message) == rest


def test_chat_answers_the_question_after_greeting(monkeypatch):
    cache_service.clear()
    session = SimpleNamespace(id=1, pending_clarification=None, last_query=None, status="active")
    monkeypatch.setattr(chat_module, "get_or_create_session", lambda db, user_id: session)
    monkeypatch.setattr(chat_module, "get_active_search_task", lambda db, session: None)
    use_case = ChatUseCase()
    use_case._handle_understanding = lambda *args, **kwargs: None
    searched = []
    use_case._handle_product_search = lambda db, user_id, message, *args, **kwargs: (
        searched.append(message) or {"type": "product_search"})

    response = use_case.process_text(db=None, user_id="u-hi", message="გამარჯობა, ქალის ფეხსაცმელი 36", locale="ka")

    assert response["type"] == "product_search"
    assert searched == ["ქალის ფეხსაცმელი 36"]