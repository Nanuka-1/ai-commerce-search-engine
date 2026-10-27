"""26.10 (шаг 4): кнопки виджета — команда action, а не текст."""
from types import SimpleNamespace

import app.use_cases.chat_use_case as chat_module
from app.schemas.chat import ChatMessageRequest
from app.services import cache_service
from app.services.translations import translate
from app.use_cases.chat_use_case import ChatUseCase


def _chat(monkeypatch, user_id):
    cache_service.clear()
    session = SimpleNamespace(id=1, pending_clarification=None, last_query=None, status="active")
    monkeypatch.setattr(chat_module, "get_or_create_session", lambda db, user_id: session)
    monkeypatch.setattr(chat_module, "get_active_search_task", lambda db, session: None)
    use_case = ChatUseCase()
    use_case._handle_understanding = lambda *args, **kwargs: None
    searched = []

    def fake_search(db, user_id, message, locale, limit, offset, resolution_reason=None, **kwargs):
        searched.append((message, kwargs))
        return {"type": "product_search", "message": "ok", "data": {"user_id": user_id}}

    use_case._handle_product_search = fake_search

    def say(text, action=None):
        return use_case.process_text(db=None, user_id=user_id, message=text, locale="ka", action=action)

    return say, searched


def test_request_accepts_action():
    request = ChatMessageRequest(user_id="u", message="კიდევ ვარიანტები", locale="ka", action="more")
    assert request.action == "more"
    assert ChatMessageRequest(user_id="u", message="ქალის ფეხსაცმელი 36", locale="ka").action is None


def test_more_button_repeats_search_with_all_conditions(monkeypatch):
    say, searched = _chat(monkeypatch, "u-more")
    say("ახალი კოლექცია ქალის ფეხსაცმელი 36 300 ლარამდე")
    say("კიდევ ვარიანტები", action="more")
    query, kwargs = searched[-1]
    assert query == "ქალის ფეხსაცმელი 36"
    assert kwargs["max_price"] == 300 and kwargs["new_only"] is True


def test_new_search_button_clears_conditions(monkeypatch):
    say, searched = _chat(monkeypatch, "u-reset-btn")
    say("ახალი კოლექცია ქალის ფეხსაცმელი 36 300 ლარამდე")
    response = say("ახალი ძებნა", action="new_search")
    assert response["message"] == translate("state_new_search", "ka")
    say("მამაკაცის ქურთუკი M")
    query, kwargs = searched[-1]
    assert query == "მამაკაცის ქურთუკი M"
    assert kwargs["max_price"] is None and kwargs["new_only"] is False


def test_more_button_without_search_asks_what_to_look_for(monkeypatch):
    say, searched = _chat(monkeypatch, "u-more-empty")
    response = say("კიდევ ვარიანტები", action="more")
    assert response["message"] == translate("state_need_product", "ka")
    assert searched == []