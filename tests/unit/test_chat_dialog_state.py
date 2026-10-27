"""22.10 (шаг 2б): тест СТЫКА — настоящие сообщения подряд через process_text, ИИ выключен (путь правил).
Живьём 21.10: «და მაინტერესებს 300ლარამდე თუ გაქვთ» → новый поиск → условия потеряны.
Юнит-тесты карточки этого не видят: им не важно, как чат передаёт сообщения в карточку и из карточки в поиск."""
from types import SimpleNamespace

import app.use_cases.chat_use_case as chat_module
from app.services import cache_service
from app.services.translations import translate
from app.use_cases.chat_use_case import ChatUseCase


def _chat(monkeypatch, user_id):
    cache_service.clear()
    session = SimpleNamespace(id=1, pending_clarification=None, last_query=None, status="active")
    monkeypatch.setattr(chat_module, "get_or_create_session", lambda db, user_id: session)
    monkeypatch.setattr(chat_module, "get_active_search_task", lambda db, session: None)
    use_case = ChatUseCase()
    use_case._handle_understanding = lambda *args, **kwargs: None      # ИИ не успел / выключен
    searched = []

    def fake_search(db, user_id, message, locale, limit, offset, resolution_reason=None, **kwargs):
        searched.append((message, kwargs))
        return {"type": "product_search", "message": "ok", "data": {"user_id": user_id}}

    use_case._handle_product_search = fake_search

    def say(text):
        return use_case.process_text(db=None, user_id=user_id, message=text, locale="ka")

    return say, searched


def test_dialog_keeps_conditions_and_asks_size(monkeypatch):
    say, searched = _chat(monkeypatch, "u-dialog")

    say("ახალი კოლექცია ქალის ფეხსაცმელი 36")
    query, kwargs = searched[-1]
    assert query == "ქალის ფეხსაცმელი 36" and kwargs["new_only"] is True

    # то, что сломалось 21.10: «მაინტერესებს / გაქვთ» — не новый товар, условия на месте
    say("და მაინტერესებს 300ლარამდე თუ გაქვთ")
    query, kwargs = searched[-1]
    assert query == "ქალის ფეხსაცმელი 36"
    assert kwargs["max_price"] == 300 and kwargs["new_only"] is True

    # смена пола → вопрос о размере, БЕЗ поиска
    response = say("მამაკაცის?")
    assert response["type"] == "clarify"
    assert response["message"] == translate("state_ask_size", "ka")
    assert len(searched) == 2

    # ответ «42» → поиск по полной карточке
    say("42")
    query, kwargs = searched[-1]
    assert query == "მამაკაცის ფეხსაცმელი 42"
    assert kwargs["max_price"] == 300 and kwargs["new_only"] is True


def test_new_search_starts_clean(monkeypatch):
    say, searched = _chat(monkeypatch, "u-reset")
    say("ახალი კოლექცია ქალის ფეხსაცმელი 36 300 ლარამდე")

    response = say("ახალი ძებნა")
    assert response["type"] == "clarify"
    assert response["message"] == translate("state_new_search", "ka")

    say("მამაკაცის ქურთუკი M")
    query, kwargs = searched[-1]
    assert query == "მამაკაცის ქურთუკი M"
    assert kwargs["max_price"] is None and kwargs["new_only"] is False


def test_short_english_dialog(monkeypatch):
    say, searched = _chat(monkeypatch, "u-en")
    say("nike")
    say("women")
    say("40")
    assert searched[-1][0] == "nike women 40"


def test_budget_without_product_asks_what_to_look_for(monkeypatch):
    say, searched = _chat(monkeypatch, "u-budget")
    response = say("300 ლარამდე")
    assert response["type"] == "clarify"
    assert response["message"] == translate("state_need_product", "ka")
    assert searched == []


def test_girl_request_searches_kids_and_says_honestly(monkeypatch):
    # 26.10: деления «девочки / мальчики» в каталоге нет — ищем детское и честно говорим
    say, searched = _chat(monkeypatch, "u-girl")
    response = say("გოგონასთვის ფეხსაცმელი 33")
    assert searched[-1][0] == "ბავშვის ფეხსაცმელი 33"
    assert response["message"].startswith(translate("kids_unisex_note", "ka"))

    response = say("ბავშვის ფეხსაცმელი 34")           # без «девочки» — без пометки
    assert not response["message"].startswith(translate("kids_unisex_note", "ka"))


def test_gibberish_mid_dialog_is_not_a_repeat(monkeypatch):
    # 26.10 (живьём): три разные бессмыслицы → три раза те же карточки «ამ პირობებით სხვა ვარიანტი არ არის»
    say, searched = _chat(monkeypatch, "u-gibberish")
    say("ქალის ფეხსაცმელი 36")
    response = say("დჯვდკლვჯლვჯლვფლ")
    assert response["type"] == "clarify"
    assert response["message"] == translate("unknown", "ka")
    assert len(searched) == 1                                  # нового поиска не было
    say("38")                                                  # разговор продолжается с той же карточкой
    assert searched[-1][0] == "ქალის ფეხსაცმელი 38"