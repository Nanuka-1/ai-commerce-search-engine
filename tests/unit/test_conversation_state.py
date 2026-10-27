"""22.10 (шаг 1, v2): карточка условий разговора — решения пользователя 21.10 (claude/dialog-state-design.md).
Только чистые функции: без базы, без ИИ, без кэша."""
from app.services.conversation_state_service import (
    ASK, CLARIFY, RESET_DONE, SEARCH, UNCLEAR,
    SearchState, describe_state, merge, patch_from_ai, patch_from_rules,
    search_filters, search_text, state_from_dict, state_to_dict,
)


def _say(state, message):
    return merge(state, patch_from_rules(message))


def test_whole_dialog_from_user_example():
    # 1. «новая коллекция, женская обувь 36» → ищем
    state, decision = _say(None, "ახალი კოლექცია ქალის ფეხსაცმელი 36")
    assert decision.action == SEARCH
    assert search_text(state) == "ქალის ფეხსაცმელი 36" and state.new_only

    # 2. «а до 300?» → всё остаётся + бюджет («მაინტერესებს / გაქვთ» не меняют товар)
    state, decision = _say(state, "და მაინტერესებს 300ლარამდე თუ გაქვთ")
    assert decision.action == SEARCH
    assert search_text(state) == "ქალის ფეხსაცმელი 36"
    assert (state.gender, state.size, state.max_price, state.new_only) == ("women", "36", 300, True)

    # 3. «а для мужчин?» → пол заменён, бюджет и новинки остались, РАЗМЕР СПРОСИТЬ (без поиска)
    state, decision = _say(state, "მამაკაცის?")
    assert (decision.action, decision.ask) == (ASK, ["size"])
    assert (state.gender, state.size, state.max_price, state.new_only) == ("men", None, 300, True)

    # 4. «42» → ищем по полной карточке
    state, decision = _say(state, "42")
    assert decision.action == SEARCH
    assert search_text(state) == "მამაკაცის ფეხსაცმელი 42" and state.max_price == 300

    # 5. «а куртку?» → обувь → одежда: размер спросить
    state, decision = _say(state, "ქურთუკი")
    assert (decision.action, decision.ask) == (ASK, ["size"])
    assert state.product == "ქურთუკი" and state.size is None

    # 6. «L» → ищем
    state, decision = _say(state, "L")
    assert decision.action == SEARCH
    assert search_text(state) == "მამაკაცის ქურთუკი L"
    assert search_filters(state)["max_price"] == 300 and search_filters(state)["new_only"] is True

    # 7. «новый поиск» → чистый лист
    state, decision = _say(state, "ახალი ძებნა")
    assert decision.action == RESET_DONE
    assert state == SearchState()


def test_filler_words_do_not_get_into_search():
    state, decision = _say(None, "ქალის ფეხსაცმელი მაინტერესებს 38 ზომა")
    assert decision.action == SEARCH
    assert search_text(state) == "ქალის ფეხსაცმელი 38"


def test_style_refinement_keeps_size():
    # «нет, спортивные» — уточнение того же товара, размер не спрашиваем
    state, _ = _say(None, "ქალის ფეხსაცმელი 36")
    state, decision = _say(state, "არა სპორტული მინდა")
    assert decision.action == SEARCH
    assert search_text(state) == "ქალის სპორტული ფეხსაცმელი 36"


def test_model_with_budget_asks_budget_and_keeps_size():
    state, _ = _say(None, "მამაკაცის ფეხსაცმელი 42 300 ლარამდე")
    state, decision = _say(state, "adidas samba")
    assert (decision.action, decision.ask) == (ASK, ["budget"])      # модель — та же обувь, размер 42 подходит
    assert state.size == "42"
    state, decision = _say(state, "იგივე")
    assert decision.action == SEARCH and state.max_price == 300


def test_budget_answer_no_removes_budget():
    state, _ = _say(None, "ფეხსაცმელი 42 300 ლარამდე")
    state, _ = _say(state, "samba")
    state, decision = _say(state, "არა")
    assert decision.action == SEARCH and state.max_price is None


def test_budget_only_when_customer_names_it():
    state, _ = _say(None, "ქალის ფეხსაცმელი 36")
    assert state.max_price is None


def test_missing_product_asks_what_to_look_for():
    _, decision = _say(None, "300 ლარამდე")
    assert (decision.action, decision.ask) == (CLARIFY, ["product"])
    _, decision = _say(None, "ქალის ფეხსაცმელი")       # размер не обязателен — показываем, клиент уточнит
    assert decision.action == SEARCH


def test_short_english_dialog_builds_query():
    # как в смоук-тесте: «nike» → «women» → «40» = «nike women 40»
    state, decision = _say(None, "nike")
    assert decision.action == SEARCH
    state, _ = _say(state, "women")
    state, decision = _say(state, "40")
    assert decision.action == SEARCH
    assert search_text(state) == "nike women 40"


def test_unknown_product_word_in_first_message_is_searched_as_is():
    state, decision = _say(None, "swimming")
    assert decision.action == SEARCH and search_text(state) == "swimming"


def test_accessory_needs_no_size():
    _, decision = _say(None, "nike ჩანთა")
    assert decision.action == SEARCH


def test_reset_with_new_request_starts_from_it():
    state, _ = _say(None, "ქალის ფეხსაცმელი 36 300 ლარამდე")
    state, decision = _say(state, "ახალი ძებნა მამაკაცის ქურთუკი M")
    assert decision.action == SEARCH
    assert search_text(state) == "მამაკაცის ქურთუკი M" and state.max_price is None


def test_ai_patch_uses_same_merge():
    state, _ = _say(None, "ახალი კოლექცია ქალის ფეხსაცმელი 36")
    result = {"query": "მამაკაცის ფეხსაცმელი", "gender": "men", "size": None, "max_price": None}
    state, decision = merge(state, patch_from_ai(result, "და კაცისთვის?"))
    assert (decision.action, decision.ask) == (ASK, ["size"])      # с ИИ — то же правило, что без него
    assert state.new_only is True


def test_ai_gender_only_in_query_is_kept():
    # ИИ: query «ბავშვის ფეხსაცმელი», а поле gender пустое — пол не должен потеряться
    result = {"query": "ბავშვის ფეხსაცმელი", "gender": None, "size": None, "max_price": 100.0}
    state, decision = merge(None, patch_from_ai(result, "ბავშვის ფეხსაცმელი 100 ლარამდე"))
    assert decision.action == SEARCH
    assert state.gender == "kids" and search_text(state) == "ბავშვის ფეხსაცმელი"


def test_girl_or_boy_means_kids_of_catalog():
    # 26.10 (замер): в каталоге детское не делится на девочек / мальчиков → ищем «ბავშვის»
    state, decision = _say(None, "გოგონასთვის ფეხსაცმელი 33")
    assert decision.action == SEARCH and state.gender == "kids"
    assert search_text(state) == "ბავშვის ფეხსაცმელი 33"
    assert patch_from_rules("გოგონასთვის ფეხსაცმელი 33").child is True
    assert patch_from_rules("ბავშვის ფეხსაცმელი 33").child is False
    # девочка → мальчик: то же «детское», размер не теряем
    state, decision = _say(state, "ბიჭისთვის?")
    assert decision.action == SEARCH and state.size == "33"


def test_describe_and_store():
    state, _ = _say(None, "ახალი კოლექცია ქალის ფეხსაცმელი 36 300 ლარამდე")
    assert describe_state(state) == "ქალის · ფეხსაცმელი · 36 · ≤ 300 ₾ · ახალი კოლექცია"
    assert state_from_dict(state_to_dict(state)) == state


def test_gibberish_in_conversation_keeps_card_and_asks_again():
    # 26.10 (живьём): «დჯვდკლვჯლვჯლვფლ» посреди разговора → «повтор» → те же карточки
    state, _ = _say(None, "ქალის ფეხსაცმელი 36 300 ლარამდე")
    new_state, decision = _say(state, "დჯვდკლვჯლვჯლვფლ")
    assert decision.action == UNCLEAR
    assert new_state == state                                  # карточка не тронута
    _, decision = _say(state, "38")                            # понятное — как раньше
    assert decision.action == SEARCH