import pytest
from app.services.intent_router import extract_size_from_query
from app.services.intent_router import detect_intent,map_category_to_db_slug,extract_color_from_query


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

@pytest.mark.parametrize("query, expected", [
    ("Nike 42", "42"),
    ("Nike 42.5", "42.5"),
    ("nike 42,5", "42.5"),
    ("Air Max 90 42", "42"),
    ("Air Force 1 44", "44"),
    ("Adidas hoodie M", "M"),
    ("under armour shorts xl", "XL"),
    ("reebok 2XL", "XXL"),
    ("Nike's shoes", None),
    ("Nike shoes", None),
    ("size 60", None),
    ("ნაიკი 42-ე ზომა", "42"),
])
def test_extract_size_from_query(query, expected):
    assert extract_size_from_query(query) == expected

@pytest.mark.parametrize("category, expected", [
    ("men", "მამაკაც"),
    ("women", "ქალ"),
    ("kids", "ბავშვ"),
    (None, None),
])
def test_map_category_to_db_slug_uses_georgian_roots(category, expected):
    assert map_category_to_db_slug(category) == expected

@pytest.mark.parametrize("query, expected", [
    ("nike grey hoodie", "gray"),
    ("adidas gray shorts", "gray"),
    ("შავი ფეხსაცმელი", "black"),
    ("navy blue hoodie", "navy"),
    ("მუქი ლურჯი მაისური", "navy"),
    ("ლურჯი შორტი", "blue"),
    ("ვარდისფერი ფეხსაცმელი", "pink"),
    ("multicolor jibbitz", "multicolor"),
    ("reebok club c", None),
])
def test_extract_color_from_query_uses_db_canonical_gray(query, expected):
    assert extract_color_from_query(query) == expected

