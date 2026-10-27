"""19.10 (п.115): «ещё / другие модели» при активном поиске → следующие 5 ТОЙ ЖЕ задачи (пол, размер, бюджет),
без вызова ИИ. Сообщение со своими словами о товаре («სხვა ფერის კედები») — обычный путь."""
from types import SimpleNamespace

import pytest

import app.use_cases.chat_use_case as chat_module
from app.services import cache_service
from app.services.conversation_state_service import SearchState, state_to_dict
from app.services.translations import translate
from app.use_cases.chat_use_case import ChatUseCase, is_more_request


@pytest.mark.parametrize("message", [
    "კიდევ სხვა მოდელი მაჩვენე",
    "მაჩვენე სხვა მოდელები",
    "კიდევ 5",
    "show me more",
    "other models?",
    "კიდე ვარიანტები შემომთავაზე",   # 19.10: живая проверка — ушло в ИИ, теперь правила
])
def test_more_requests(message):
    assert is_more_request(message) is True


@pytest.mark.parametrize("message", [
    "სხვა ფერის კედები",          # свой товар → новый поиск
    "სხვა ბრენდის მოდელები",      # другой бренд → не «ещё того же»
    "კიდევ 43",                   # новый размер → уточнение
    "ქალის ფეხსაცმელი 36",        # обычный поиск
    "მაჩვენე",                    # нет слова «ещё / другие»
    "",
])
def test_not_more_requests(message):
    assert is_more_request(message) is False


def _use_case(monkeypatch, active_task):
    """Чат без базы: сессия и активная задача подменены, вызовы «следующих 5» и ИИ записываются."""
    cache_service.clear()
    monkeypatch.setattr(chat_module, "get_or_create_session", lambda db, user_id: SimpleNamespace(id=1))
    monkeypatch.setattr(chat_module, "get_active_search_task", lambda db, session: active_task)
    use_case = ChatUseCase()
    calls = {"more": [], "understanding": 0}

    def fake_more(db, user_id, query, locale, limit, offset, resolution_reason, **kwargs):
        calls["more"].append({"query": query, **kwargs})
        return {"type": "product_search", "message": "more", "data": {"user_id": user_id}}

    def fake_understanding(*args, **kwargs):
        calls["understanding"] += 1
        return {"type": "understood", "message": "ai", "data": {}}

    use_case._show_more_or_same = fake_more
    use_case._handle_understanding = fake_understanding
    return use_case, calls


def test_more_request_keeps_conditions_without_ai(monkeypatch):
    task = SimpleNamespace(query="ქალის ფეხსაცმელი 36")
    use_case, calls = _use_case(monkeypatch, task)
    # 26.10: условия разговора — в карточке (раньше текст задачи + chat:deal)
    cache_service.set("chat:state:u1", state_to_dict(SearchState(
        gender="women", gender_word="ქალის", product="ფეხსაცმელი", product_text="ფეხსაცმელი", size="36",
        max_price=100, discount_only=True)))

    response = use_case.process_text(db=None, user_id="u1", message="კიდევ სხვა მოდელი მაჩვენე", locale="ka")

    assert response["message"] == "more"
    assert calls["understanding"] == 0                      # ИИ не звали
    assert calls["more"][0]["query"] == "ქალის ფეხსაცმელი 36"   # пол и размер из карточки
    assert calls["more"][0]["max_price"] == 100             # бюджет и скидка — как в прошлом поиске
    assert calls["more"][0]["discount_only"] is True


def test_product_words_go_normal_way(monkeypatch):
    use_case, calls = _use_case(monkeypatch, SimpleNamespace(query="ქალის ფეხსაცმელი 36 ზომა"))

    response = use_case.process_text(db=None, user_id="u2", message="სხვა ფერის კედები", locale="ka")

    assert response["type"] == "understood"
    assert calls["more"] == []


def test_without_active_task_goes_normal_way(monkeypatch):
    use_case, calls = _use_case(monkeypatch, None)

    response = use_case.process_text(db=None, user_id="u3", message="მაჩვენე სხვა მოდელები", locale="ka")

    assert response["type"] == "understood"
    assert calls["more"] == []


def test_more_answer_is_marked_as_template():
    # текст «აი სხვა ვარიანტები 👇» — наш шаблон, значок «✨ AI პასუხი» показывать нельзя
    cache_service.clear()
    cache_service.set("chat:shown:u4", ["page-1"])
    use_case = ChatUseCase()
    use_case._handle_product_search = lambda *args, **kwargs: {
        "message": "ai text",
        "meta": {"ai_used": True, "ai_mode": "llm"},
        "data": {"results": {"items": [{"product_url": "page-2"}]}},
    }

    response = use_case._show_more_or_same(None, "u4", "q", "ka", 5, 0, "more_request")

    assert response["message"] == translate("repeat_more", "ka")
    assert response["meta"]["ai_used"] is False