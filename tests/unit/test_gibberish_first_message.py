"""26.10: бессмыслица ПЕРВЫМ сообщением («ватлдвлвдыа» → 5 женских топов Adidas).
Замер measure_semantic_floor: смысловой поиск даёт бессмыслице 0.59–0.67, настоящим словам 0.63–0.75 —
порог не разделяет («ქწერტ» 0.670 > «swimming» 0.641). Решение: если ИИ не успел, незнакомые слова без товара /
бренда / модели показываем, только если нашлось ПО СЛОВАМ; иначе «не поняла». Бессмыслица в карточке не остаётся."""
from types import SimpleNamespace

import pytest

import app.use_cases.chat_use_case as chat_module
from app.services import cache_service
from app.services.conversation_state_service import SEARCH, SearchState, merge, patch_from_rules, search_text
from app.services.translations import translate
from app.use_cases.chat_use_case import ChatUseCase


def test_unknown_words_replace_previous_unknown_words():
    state, _ = merge(None, patch_from_rules("ватлдвлвдыа"))
    state, decision = merge(state, patch_from_rules("swimming"))
    assert decision.action == SEARCH and search_text(state) == "swimming"


def test_unknown_words_after_new_search_are_searched():
    _, decision = merge(SearchState(), patch_from_rules("swimming"))       # пустая карточка после кнопки
    assert decision.action == SEARCH


def _chat(monkeypatch, user_id, semantic_only):
    cache_service.clear()
    monkeypatch.setattr(chat_module, "get_or_create_session",
                        lambda db, user_id: SimpleNamespace(id=1, pending_clarification=None, last_query=None))
    monkeypatch.setattr(chat_module, "get_active_search_task", lambda db, session: None)
    use_case = ChatUseCase()
    use_case._handle_understanding = lambda *args, **kwargs: None      # ИИ не успел
    calls = []

    def fake_search(db, user_id, message, locale, limit, offset, resolution_reason=None, **kwargs):
        calls.append((message, kwargs.get("keyword_required", False)))
        if kwargs.get("keyword_required") and semantic_only:
            return None                                                 # по словам 0, только смысловой
        return {"type": "product_search", "message": "ok", "data": {"user_id": user_id}}

    use_case._handle_product_search = fake_search

    def say(text):
        return use_case.process_text(db=None, user_id=user_id, message=text, locale="ka")

    return say, calls


def test_gibberish_first_message_says_not_understood(monkeypatch):
    say, calls = _chat(monkeypatch, "u-gib1", semantic_only=True)
    response = say("ватлдвлвдыа")
    assert response["type"] == "clarify"
    assert response["message"] == translate("unknown", "ka")
    assert calls == [("ватлдвлвдыа", True)]
    assert "ватлдвлвдыа" not in response["meta"]["dialog_state"]        # не осталась «товаром»


def test_known_product_does_not_need_keyword_confirmation(monkeypatch):
    say, calls = _chat(monkeypatch, "u-gib2", semantic_only=True)
    say("ქალის ფეხსაცმელი 36")
    assert calls[-1] == ("ქალის ფეხსაცმელი 36", False)


def test_unknown_word_found_by_keywords_is_shown(monkeypatch):
    say, calls = _chat(monkeypatch, "u-gib3", semantic_only=False)     # «yoga» есть в названиях
    response = say("yoga")
    assert response["type"] == "product_search"


class _Products(SimpleNamespace):
    pass


@pytest.mark.parametrize("matched_by, expected_none", [("semantic", True), ("query", False)])
def test_product_search_returns_none_only_for_semantic_only(monkeypatch, matched_by, expected_none):
    items = [{"product_url": "https://topsport.ge/ka/product/a?size=S"}]
    monkeypatch.setattr(chat_module, "search_products", lambda db, request: _Products(
        items=list(items), total_count=1, result_mode="found", query="q", matched_by=matched_by))
    monkeypatch.setattr(chat_module, "apply_search_decision", lambda products, request: products)
    monkeypatch.setattr(chat_module, "resolve_next_step", lambda mode: None)
    monkeypatch.setattr(chat_module, "sync_search_task_after_result", lambda **kwargs: None)
    monkeypatch.setattr(chat_module, "build_response", lambda products, user_id, kind, locale, **kwargs: {
        "type": kind, "message": "found", "data": {"results": {"items": list(products.items)}}})
    monkeypatch.setattr(chat_module, "enhance_response", lambda base, products, **kwargs: base)
    monkeypatch.setattr(chat_module, "scarce_sizes_by_page", lambda db, pages: {})
    monkeypatch.setattr(chat_module, "log_after_response", lambda *args, **kwargs: None)
    cache_service.clear()

    response = ChatUseCase()._handle_product_search(None, "u-gib4", "ватлдвлвдыа", "ka", 5, 0,
                                                     session=None, active_task=None, keyword_required=True)

    assert (response is None) is expected_none