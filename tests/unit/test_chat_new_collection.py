"""21.10 (этап 3, шаг 3б): чат передаёт «только новинки» в поиск и в факты для ИИ."""
from types import SimpleNamespace

import pytest

import app.use_cases.chat_use_case as chat_module
from app.services import cache_service
from app.services.llm_text_service import describe_conditions
from app.use_cases.chat_use_case import ChatUseCase


def test_conditions_for_ai_say_new_collection():
    conditions = describe_conditions(size="36", new_only=True)
    assert "new collection" in conditions          # тогда проверка честности (new_claim) пропустит «ახალი კოლექცია»
    assert describe_conditions(size="36") == "size 36"   # без новинок — как раньше


def test_rules_path_passes_new_only_and_cleans_query(monkeypatch):
    cache_service.clear()
    session = SimpleNamespace(id=1, pending_clarification=None, last_query=None, status="active")
    monkeypatch.setattr(chat_module, "get_or_create_session", lambda db, user_id: session)
    monkeypatch.setattr(chat_module, "get_active_search_task", lambda db, session: None)
    use_case = ChatUseCase()
    use_case._handle_understanding = lambda *args, **kwargs: None      # ИИ не помог → путь правил
    searched = []

    def fake_search(db, user_id, message, locale, limit, offset, resolution_reason=None, **kwargs):
        searched.append((message, kwargs))
        return {"type": "product_search", "message": "ok", "data": {"user_id": user_id}}

    use_case._handle_product_search = fake_search

    use_case.process_text(db=None, user_id="u-new", message="ქალის ახალი კოლექცია ფეხსაცმელი 36", locale="ka")

    message, kwargs = searched[0]
    assert message == "ქალის ფეხსაცმელი 36"        # слова о новинках убраны из текста поиска
    assert kwargs["new_only"] is True


class _Stop(Exception):
    """Останавливаем _handle_product_search сразу после поиска — дальше (база, ИИ) этому тесту не нужно."""


def test_product_search_really_sends_new_only_to_search(monkeypatch):
    # 21.10: именно здесь была тихая ошибка — `if new_only` оказался внутри `if prefer_discount`,
    # и фильтр не включался. Остальные тесты её не видели: они подменяли _handle_product_search целиком.
    captured = []

    def fake_search_products(db, request):
        captured.append(request)
        raise _Stop

    monkeypatch.setattr(chat_module, "search_products", fake_search_products)

    with pytest.raises(_Stop):
        ChatUseCase()._handle_product_search(None, "u-new", "ქალის ფეხსაცმელი 36", "ka", 5, 0,
                                             session=None, active_task=None, new_only=True)

    assert captured[0].new_only is True                 # без «сначала со скидкой» — фильтр всё равно включён
    assert captured[0].prefer_discount is False