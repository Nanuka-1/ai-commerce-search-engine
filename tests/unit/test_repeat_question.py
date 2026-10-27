"""15.10 (решение пользователя): клиент повторил тот же вопрос → следующие 5 вариантов;
если новых нет — те же карточки (а не пустое «других нет»)."""
from types import SimpleNamespace

from app.services import cache_service
from app.services.translations import translate
from app.use_cases import chat_use_case as module
from app.use_cases.chat_use_case import ChatUseCase

PAGE = "https://topsport.ge/ka/product/"


def _stubs(monkeypatch, items):
    # каждый поиск возвращает НОВЫЙ объект (иначе фильтр «кроме показанных» испортит общий список)
    monkeypatch.setattr(module, "search_products", lambda db, request: SimpleNamespace(
        items=list(items), total_count=len(items), result_mode="found", query="q"))
    monkeypatch.setattr(module, "apply_search_decision", lambda products, request: products)
    monkeypatch.setattr(module, "resolve_next_step", lambda mode: None)
    monkeypatch.setattr(module, "sync_search_task_after_result", lambda **kwargs: None)
    monkeypatch.setattr(module, "build_response", lambda products, user_id, kind, locale, **kwargs: {
        "type": kind, "message": "found", "data": {"results": {"items": list(products.items)}}})
    monkeypatch.setattr(module, "enhance_response", lambda base, products, **kwargs: base)
    monkeypatch.setattr(module, "scarce_sizes_by_page", lambda db, pages: {})
    monkeypatch.setattr(module, "log_search_event", lambda **kwargs: None)


def _run(user_id):
    return ChatUseCase()._show_more_or_same(None, user_id, "q", "ka", 5, 0, None, session=None, active_task=None)


def test_repeat_shows_next_options(monkeypatch):
    _stubs(monkeypatch, [{"product_url": f"{PAGE}a?size=S"}, {"product_url": f"{PAGE}c?size=S"}])
    cache_service.set("chat:shown:u-rep1", [f"{PAGE}a"], ttl=60)
    response = _run("u-rep1")
    assert [item["product_url"] for item in response["data"]["results"]["items"]] == [f"{PAGE}c?size=S"]
    assert response["message"] == translate("repeat_more", "ka")


def test_repeat_without_new_options_shows_same(monkeypatch):
    _stubs(monkeypatch, [{"product_url": f"{PAGE}a?size=S"}])
    cache_service.set("chat:shown:u-rep2", [f"{PAGE}a"], ttl=60)
    response = _run("u-rep2")
    assert [item["product_url"] for item in response["data"]["results"]["items"]] == [f"{PAGE}a?size=S"]
    assert response["message"] == translate("repeat_same", "ka")