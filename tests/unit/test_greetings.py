import pytest

from app.services.intent_router import detect_intent


@pytest.mark.parametrize("message", [
    "მოგესალმებით", "მოგესალმებით!", "გამარჯობათ", "სალამი", "ჰაი",
    "დილა მშვიდობისა", "საღამო მშვიდობისა", "hello", "Hello there", "გამარჯობა",
])
def test_greetings_are_not_product_search(message):
    assert detect_intent(message) == "greeting"


@pytest.mark.parametrize("message", ["სარბენი ფეხსაცმელი 42", "nike 42", "hoodie M"])
def test_product_queries_stay_search(message):
    assert detect_intent(message) == "product_search"