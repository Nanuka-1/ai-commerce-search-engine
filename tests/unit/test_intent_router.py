from app.services.intent_router import detect_intent


def test_empty_message():
    assert detect_intent("") == "empty"


def test_greeting_en():
    assert detect_intent("hello") == "greeting"


def test_greeting_ka():
    assert detect_intent("გამარჯობა") == "greeting"


def test_price_check_en():
    assert detect_intent("price CW2288-111") == "price_check"


def test_price_check_how_much():
    assert detect_intent("how much is CW2288-111") == "price_check"


def test_price_check_ka():
    assert detect_intent("რა ღირს CW2288-111") == "price_check"


def test_sku_search():
    assert detect_intent("CW2288-111") == "sku_search"


def test_product_search():
    assert detect_intent("Nike Air") == "product_search"


def test_price_without_sku():
    assert detect_intent("price") == "price_check"


def test_greeting_with_extra_spaces():
    assert detect_intent("   hello   ") == "greeting"


def test_price_check_with_extra_spaces():
    assert detect_intent("   price    CW2288-111   ") == "price_check"


def test_sku_search_lowercase():
    assert detect_intent("cw2288-111") == "sku_search"


def test_price_check_uppercase_message():
    assert detect_intent("PRICE CW2288-111") == "price_check"


def test_product_search_with_multiple_spaces():
    assert detect_intent("Nike    Air") == "product_search"


def test_empty_message_with_spaces_only():
    assert detect_intent("      ") == "empty"

def test_how_much_without_sku():
    assert detect_intent("how much is") == "price_check"


def test_price_check_ka_without_sku():
    assert detect_intent("რა ღირს") == "price_check"