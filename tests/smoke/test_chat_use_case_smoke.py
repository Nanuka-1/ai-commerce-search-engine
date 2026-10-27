from app.use_cases.chat_use_case import ChatUseCase
from app.services.translations import TRANSLATIONS
from types import SimpleNamespace

def test_chat_use_case_greeting(db):
    use_case = ChatUseCase()

    result = use_case.process_text(
        db=db,
        user_id="smoke_user",
        message="hello",
        locale="en",
    )

    assert result["type"] == "greeting"

def test_chat_use_case_empty_message(db):
    use_case = ChatUseCase()

    result = use_case.process_text(
        db=db,
        user_id="smoke_user",
        message="",
        locale="en",
    )

    assert result["type"] == "empty"

def test_chat_use_case_product_search(db):
    use_case = ChatUseCase()

    result = use_case.process_text(
        db=db,
        user_id="smoke_user",
        message="nike",
        locale="en",
    )

    assert result["type"] == "product_search"

def test_chat_use_case_duplicate_request(db):
    use_case = ChatUseCase()

    # First request
    use_case.process_text(
        db=db,
        user_id="duplicate_user",
        message="nike",
        locale="en",
    )

    # Second request
    result = use_case.process_text(
        db=db,
        user_id="duplicate_user",
        message="nike",
        locale="en",
    )

    assert result["type"] == "product_search"  # 19.10: повтор → следующие варианты, не «уже обработано»

def test_chat_use_case_sku_search(db):
    use_case = ChatUseCase()

    result = use_case.process_text(
        db=db,
        user_id="sku_user",
        message="HQ8111-300-39",
        locale="en",
    )

    assert result["type"] == "sku_search"

def test_chat_use_case_price_check(db):
    use_case = ChatUseCase()

    result = use_case.process_text(
        db=db,
        user_id="price_user",
        message="price HQ8111-300-39",
        locale="en",
    )

    assert result["type"] == "price_check"

def test_chat_use_case_conversation_flow(db):
    use_case = ChatUseCase()

    use_case.process_text(
        db=db,
        user_id="conversation_user",
        message="nike",
        locale="en",
    )

    use_case.process_text(
        db=db,
        user_id="conversation_user",
        message="women",
        locale="en",
    )

    result = use_case.process_text(
        db=db,
        user_id="conversation_user",
        message="39",
        locale="en",
    )

    assert result["type"] == "product_search"

def test_chat_use_case_price_check_missing_identifier(db):
    use_case = ChatUseCase()

    result = use_case.process_text(
        db=db,
        user_id="price_missing_user",
        message="price",
        locale="en",
    )

    assert result["type"] == "price_check"
    assert "message" in result

def test_chat_use_case_build_sku_response_not_found():
    use_case = ChatUseCase()

    product_result = SimpleNamespace(
        items=[],
        base_sku="UNKNOWN-SKU",
        detected_size=None,
    )

    result = use_case._build_sku_response(
        user_id="sku_not_found_user",
        product_result=product_result,
        locale="en",
    )

    assert result["type"] == "sku_search"
    assert result["data"]["results"]["sku"] == "UNKNOWN-SKU"
    assert result["data"]["results"]["item"] is None
    assert "message" in result


def test_chat_use_case_build_price_response_not_found():
    use_case = ChatUseCase()

    product_result = SimpleNamespace(
        items=[],
        base_sku="UNKNOWN-SKU",
    )

    result = use_case._build_price_response(
        user_id="price_not_found_user",
        product_result=product_result,
        locale="en",
    )

    assert result["type"] == "price_check"
    assert result["data"]["results"]["sku"] == "UNKNOWN-SKU"
    assert result["data"]["results"]["price"] is None
    assert "message" in result


def test_chat_use_case_price_check_by_query(db):
    use_case = ChatUseCase()

    result = use_case.process_text(
        db=db,
        user_id="price_query_user",
        message="price nike",
        locale="en",
    )

    assert result["type"] == "price_check"

def test_chat_use_case_brand_change_restarts_conversation(db):
    use_case = ChatUseCase()

    use_case.process_text(
        db=db,
        user_id="brand_change_user",
        message="nike women 39",
        locale="en",
    )

    result = use_case.process_text(
        db=db,
        user_id="brand_change_user",
        message="adidas",
        locale="en",
    )

    assert result["type"] == "product_search"

def test_chat_use_case_thanks_after_search(db):
    use_case = ChatUseCase()

    use_case.process_text(
        db=db,
        user_id="thanks_user",
        message="nike",
        locale="en",
    )

    use_case.process_text(
        db=db,
        user_id="thanks_user",
        message="women",
        locale="en",
    )

    use_case.process_text(
        db=db,
        user_id="thanks_user",
        message="39",
        locale="en",
    )

    result = use_case.process_text(
        db=db,
        user_id="thanks_user",
        message="thanks",
        locale="en",
    )

    print(result)

    assert result["type"] == "gratitude"
    assert result["message"] == "You're welcome."
    assert result["data"]["user_id"] == "thanks_user"

def test_chat_use_case_dialog_gap_diagnostics(db):
    use_case = ChatUseCase()

    messages_to_check = [
        "thanks",
        "thank you",
        "ok thanks",
        "hello",
        "hi",
        "bye",
        "good bye",
        "спасибо",
        "мадლობა",
    ]

    for index, message in enumerate(messages_to_check):
        user_id = f"dialog_gap_user_{index}"

        use_case.process_text(
            db=db,
            user_id=user_id,
            message="nike",
            locale="en",
        )

        use_case.process_text(
            db=db,
            user_id=user_id,
            message="women",
            locale="en",
        )

        use_case.process_text(
            db=db,
            user_id=user_id,
            message="39",
            locale="en",
        )

        result = use_case.process_text(
            db=db,
            user_id=user_id,
            message=message,
            locale="en",
        )

        print(message, "=>", result["type"], result.get("message"))

def test_chat_use_case_size_change_after_search_diagnostics(db):
    use_case = ChatUseCase()

    use_case.process_text(
        db=db,
        user_id="size_change_user",
        message="nike",
        locale="en",
    )

    use_case.process_text(
        db=db,
        user_id="size_change_user",
        message="women",
        locale="en",
    )

    use_case.process_text(
        db=db,
        user_id="size_change_user",
        message="39",
        locale="en",
    )

    result = use_case.process_text(
        db=db,
        user_id="size_change_user",
        message="40",
        locale="en",
    )

    print(result)

    assert result["type"] == "product_search"

    assert result["data"]["results"]["query"] == "nike women 40"

    assert result["data"]["results"]["search_strategy"] == "brand_size"


def test_chat_use_case_model_size_update_diagnostics(db):
    use_case = ChatUseCase()

    use_case.process_text(
        db=db,
        user_id="model_size_user",
        message="nike air max",
        locale="en",
    )

    result = use_case.process_text(
        db=db,
        user_id="model_size_user",
        message="42",
        locale="en",
    )

    print(result)

    assert result["type"] == "product_search"
    assert result["data"]["results"]["query"] == "nike air max 42"
    assert result["data"]["results"]["search_strategy"] == "model_search"


def test_chat_use_case_model_change_diagnostics(db):
    use_case = ChatUseCase()

    use_case.process_text(
        db=db,
        user_id="model_change_user",
        message="nike air max",
        locale="en",
    )

    result = use_case.process_text(
        db=db,
        user_id="model_change_user",
        message="jordan",
        locale="en",
    )

    print(result)

    assert result["type"] == "product_search"


def test_chat_use_case_bye_after_search_diagnostics(db):
    use_case = ChatUseCase()

    use_case.process_text(
        db=db,
        user_id="bye_user",
        message="nike",
        locale="en",
    )

    use_case.process_text(
        db=db,
        user_id="bye_user",
        message="women",
        locale="en",
    )

    use_case.process_text(
        db=db,
        user_id="bye_user",
        message="39",
        locale="en",
    )

    result = use_case.process_text(
        db=db,
        user_id="bye_user",
        message="bye",
        locale="en",
    )

    print(result)

    assert result["type"] == "farewell"
    assert result["message"] == "Goodbye."
    assert result["data"]["user_id"] == "bye_user"

def test_chat_use_case_thanks_after_search_diagnostics(db):
    use_case = ChatUseCase()

    use_case.process_text(
        db=db,
        user_id="thanks_diagnostic_user",
        message="nike",
        locale="en",
    )

    use_case.process_text(
        db=db,
        user_id="thanks_diagnostic_user",
        message="women",
        locale="en",
    )

    use_case.process_text(
        db=db,
        user_id="thanks_diagnostic_user",
        message="39",
        locale="en",
    )

    result = use_case.process_text(
        db=db,
        user_id="thanks_diagnostic_user",
        message="thanks",
        locale="en",
    )

    print(result)

    assert result is not None

def test_chat_use_case_hello_after_search_diagnostics(db):
    use_case = ChatUseCase()

    use_case.process_text(
        db=db,
        user_id="hello_diagnostic_user",
        message="nike",
        locale="en",
    )

    use_case.process_text(
        db=db,
        user_id="hello_diagnostic_user",
        message="women",
        locale="en",
    )

    use_case.process_text(
        db=db,
        user_id="hello_diagnostic_user",
        message="39",
        locale="en",
    )

    result = use_case.process_text(
        db=db,
        user_id="hello_diagnostic_user",
        message="hello",
        locale="en",
    )

    print(result)

    assert result["type"] == "greeting"
    assert "Hello!" in result["message"]

def test_chat_use_case_small_talk_after_search_diagnostics(db):
    use_case = ChatUseCase()

    use_case.process_text(
        db=db,
        user_id="small_talk_user",
        message="nike",
        locale="en",
    )

    use_case.process_text(
        db=db,
        user_id="small_talk_user",
        message="women",
        locale="en",
    )

    use_case.process_text(
        db=db,
        user_id="small_talk_user",
        message="39",
        locale="en",
    )

    result = use_case.process_text(
        db=db,
        user_id="small_talk_user",
        message="ok",
        locale="en",
    )

    print(result)

    assert result is not None

def test_chat_use_case_product_search_does_not_duplicate_session_lookups(db, monkeypatch):
    from app.use_cases import chat_use_case as chat_use_case_module

    call_counts = {"session": 0, "active_task": 0}

    original_get_or_create_session = chat_use_case_module.get_or_create_session
    original_get_active_search_task = chat_use_case_module.get_active_search_task

    def counting_get_or_create_session(*args, **kwargs):
        call_counts["session"] += 1
        return original_get_or_create_session(*args, **kwargs)

    def counting_get_active_search_task(*args, **kwargs):
        call_counts["active_task"] += 1
        return original_get_active_search_task(*args, **kwargs)

    monkeypatch.setattr(chat_use_case_module, "get_or_create_session", counting_get_or_create_session)
    monkeypatch.setattr(chat_use_case_module, "get_active_search_task", counting_get_active_search_task)

    use_case = chat_use_case_module.ChatUseCase()

    use_case.process_text(
        db=db,
        user_id="query_efficiency_user",
        message="nike",
        locale="en",
    )

    assert call_counts["session"] == 1
    assert call_counts["active_task"] == 1


def test_chat_answers_in_georgian_when_message_is_georgian(db):
    use_case = ChatUseCase()

    result = use_case.process_text(
        db=db,
        user_id="georgian_user",
        message="ნაიკი",
        locale="en",
    )

    assert result["type"] == "product_search"
    assert any("\u10a0" <= char <= "\u10ff" for char in result["message"])


def test_chat_short_answer_follows_site_locale_for_latin_message(db):
    use_case = ChatUseCase()

    result = use_case._handle_gratitude("u", "ka")

    assert result["message"] == TRANSLATIONS["ka"]["gratitude"]


def test_build_search_response_accepts_dict_items():
    from types import SimpleNamespace

    products = SimpleNamespace(
        query="nike",
        detected_size=None,
        items=[{"id": 1, "sku": "A-42", "name": "Nike A", "price": 100.0}],
    )

    result = ChatUseCase()._build_search_response("price_check", "u", products, "en")

    assert result["data"]["results"]["items"][0]["sku"] == "A-42"