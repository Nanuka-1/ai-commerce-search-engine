"""19.10: правила узнали повтор (resolution.should_search=False) → чат не пишет «запрос уже обработан»,
а показывает следующие варианты того же поиска (новых нет → те же) — через _show_more_or_same."""
from types import SimpleNamespace

import app.use_cases.chat_use_case as chat_module
from app.services import cache_service
from app.services.conversation_state_service import SearchState, state_to_dict
from app.use_cases.chat_use_case import ChatUseCase


def test_duplicate_request_shows_more_instead_of_dry_answer(monkeypatch):
    cache_service.clear()
    # 26.10: условия разговора — в карточке (раньше chat:deal)
    cache_service.set("chat:state:u5", state_to_dict(SearchState(brand="nike", size="42", max_price=150,
                                                                 prefer_discount=True)))
    monkeypatch.setattr(chat_module, "get_or_create_session", lambda db, user_id: SimpleNamespace(id=1))
    monkeypatch.setattr(chat_module, "get_active_search_task",
                        lambda db, session: SimpleNamespace(query="nike 42"))
    monkeypatch.setattr(chat_module, "resolve_message_from_active_task",
                        lambda task, message: SimpleNamespace(should_search=False, query="nike 42",
                                                              reason="duplicate"))
    use_case = ChatUseCase()
    use_case._handle_understanding = lambda *args, **kwargs: None      # ИИ не помог → путь правил
    calls = []

    def fake_more(db, user_id, query, locale, limit, offset, resolution_reason, **kwargs):
        calls.append({"query": query, "reason": resolution_reason, **kwargs})
        return {"type": "product_search", "message": "more", "data": {"user_id": user_id}}

    use_case._show_more_or_same = fake_more

    result = use_case.process_text(db=None, user_id="u5", message="nike 42", locale="en")

    assert result["type"] == "product_search"                # не "duplicate"
    assert calls[0]["query"] == "nike 42"                    # тот же поиск
    assert calls[0]["max_price"] == 150                      # с теми же условиями
    assert calls[0]["prefer_discount"] is True