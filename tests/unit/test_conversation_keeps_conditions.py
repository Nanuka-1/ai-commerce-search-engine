"""21.10: продолжение разговора не теряет условия (бюджет, скидку, новинки).
Живьём: «ახალი კოლექცია… 36» → «…200 ლარში?» → «არა, სპორტული მინდა» — на 3-м пропали новинки."""
from types import SimpleNamespace

import app.use_cases.chat_use_case as chat_module
from app.services import cache_service
from app.services.conversation_state_service import SearchState, state_to_dict
from app.services.llm_understanding_service import UNDERSTANDING_INSTRUCTION, parse_understanding
from app.use_cases.chat_use_case import ChatUseCase


def _json(**search) -> str:
    return '{"intent": "product_search", "language": "ka", "search": %s}' % (
        str({"query": "ქალის სპორტული ფეხსაცმელი 36", **search}).replace("'", '"').replace("True", "true"))


# --- А: ИИ возвращает и помнит new_only ---

def test_ai_answer_has_new_only():
    assert parse_understanding(_json(new_only=True))["new_only"] is True
    assert parse_understanding(_json())["new_only"] is False


def test_instruction_asks_to_keep_new_only_in_conversation():
    assert '"new_only"' in UNDERSTANDING_INSTRUCTION
    assert "new_only unless the customer changed" in UNDERSTANDING_INSTRUCTION


def test_ai_path_passes_new_only_even_without_the_word(monkeypatch):
    # «არა, სპორტული მინდა» — слова «ახალი» нет, но ИИ из разговора помнит: новинки
    monkeypatch.setattr(chat_module.llm_client, "is_enabled", lambda: True)
    monkeypatch.setattr(chat_module, "needs_understanding", lambda *args, **kwargs: True)
    result = parse_understanding(_json(new_only=True, max_price=200, gender="women", size="36"))
    monkeypatch.setattr(chat_module, "understand", lambda *args, **kwargs: {
        "result": result, "model": "test", "ms": 1, "errors": []})
    use_case = ChatUseCase()
    searched = []
    use_case._handle_product_search = lambda db, user_id, message, *args, **kwargs: (
        searched.append(kwargs) or {"type": "product_search"})

    use_case._handle_understanding(None, "u-ai", "არა სპორტული მინდა", "ka", 5, 0,
                                   session=None, active_task=None, history=["ახალი კოლექცია ქალის 36"])

    assert searched[0]["new_only"] is True
    assert searched[0]["max_price"] == 200


# --- Б (22.10, шаг 2б): путь правил (ИИ не успел) — условия живут в карточке chat:state ---

CARD = SearchState(gender="women", gender_word="ქალის", product="ფეხსაცმელი", product_text="ფეხსაცმელი",
                   size="36", max_price=200, new_only=True)


def _rules_path(monkeypatch, user_id: str, message: str):
    cache_service.clear()
    cache_service.set(f"chat:state:{user_id}", state_to_dict(CARD))      # карточка после прошлого поиска
    session = SimpleNamespace(id=1, pending_clarification=None, last_query=None, status="active")
    monkeypatch.setattr(chat_module, "get_or_create_session", lambda db, user_id: session)
    monkeypatch.setattr(chat_module, "get_active_search_task",
                        lambda db, session: SimpleNamespace(query="ქალის ფეხსაცმელი 36"))
    monkeypatch.setattr(chat_module, "resolve_message_from_active_task",
                        lambda task, message: SimpleNamespace(should_search=True, query=message,
                                                              reason="continue_task"))
    use_case = ChatUseCase()
    use_case._handle_understanding = lambda *args, **kwargs: None      # ИИ не успел
    searched = []
    use_case._handle_product_search = lambda db, user_id, message, *args, **kwargs: (
        searched.append((message, kwargs)) or {"type": "product_search"})
    use_case.process_text(db=None, user_id=user_id, message=message, locale="ka")
    return searched[0]


def test_rules_continuation_keeps_previous_conditions(monkeypatch):
    query, kwargs = _rules_path(monkeypatch, "u-cont", "სპორტული")
    assert query == "ქალის სპორტული ფეხსაცმელი 36"
    assert kwargs["new_only"] is True
    assert kwargs["max_price"] == 200


def test_rules_new_search_starts_clean(monkeypatch):
    query, kwargs = _rules_path(monkeypatch, "u-restart", "ახალი ძებნა მამაკაცის ქურთუკი M")
    assert query == "მამაკაცის ქურთუკი M"
    assert kwargs["new_only"] is False
    assert kwargs["max_price"] is None