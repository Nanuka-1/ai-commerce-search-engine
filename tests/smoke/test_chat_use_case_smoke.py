from app.use_cases.chat_use_case import ChatUseCase
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

    assert result["type"] == "duplicate"

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