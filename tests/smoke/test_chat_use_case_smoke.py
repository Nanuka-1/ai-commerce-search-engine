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