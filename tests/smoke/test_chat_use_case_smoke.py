from app.use_cases.chat_use_case import ChatUseCase


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