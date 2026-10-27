from types import SimpleNamespace

import pytest

from app.schemas.search_context import SearchContext
from app.services.response_builder import build_response, build_site_search_url
from app.services.translations import TRANSLATIONS


def _product(product_id: int):
    return SimpleNamespace(id=product_id, sku=f"SKU-{product_id}", name=f"Product {product_id}", price=100.0,
                           product_url=f"https://topsport.ge/ka/product/p-{product_id}", is_active=True)


def _context(**overrides):
    values = dict(query="nike 42", normalized_query="nike 42", matched_by="query",
                  items=[_product(1), _product(2)], total_count=2, limit=5, offset=0)
    values.update(overrides)
    return SearchContext(**values)


@pytest.mark.parametrize("query, size, language, expected", [
    ("adidas samba 46", "46", "en", "https://topsport.ge/en/products?term=adidas+samba&search_type=name"),
    ("warm jacket M", "M", "en", "https://topsport.ge/en/products?term=warm+jacket&search_type=name"),
    ("nike 42.5", "42.5", "ka", "https://topsport.ge/ka/products?term=nike&search_type=name"),
    ("42", "42", "ka", "https://topsport.ge/ka/products?term=42&search_type=name"),   # только размер — не пустой term
    ("pegasus 41", None, "en", "https://topsport.ge/en/products?term=pegasus+41&search_type=name"),
])
def test_build_site_search_url(query, size, language, expected):
    assert build_site_search_url(query, size, language) == expected


def test_not_found_suggests_what_to_change_without_dead_link():
    # 13.10: поиск сайта ищет фразу целиком → ссылка часто давала пустую страницу; в тексте её больше нет
    context = _context(query="ქალის ჯემპრი", items=[], total_count=0)
    response = build_response(context, user_id="u", response_type="product_search")
    assert response["message"] == TRANSLATIONS["ka"]["search_no_products"]
    assert "https://" not in response["message"]


def test_size_not_found_says_so_without_link():
    context = _context(query="adidas samba 46", detected_size="46", items=[], total_count=0)
    message = build_response(context, user_id="u", response_type="product_search", locale="en")["message"]
    assert message == "Unfortunately, I couldn't find size 46. Try a neighbouring size or another model."


def test_size_alternatives_without_site_link():
    context = _context(detected_size="42", matched_by="size_alternatives")
    message = build_response(context, user_id="u", response_type="product_search", locale="en")["message"]
    assert "Showing alternative products available in size 42" in message
    assert "https://" not in message


def test_found_in_size_is_emphasized_and_url_in_data():
    response = build_response(_context(detected_size="42"), user_id="u", response_type="product_search", locale="en")
    assert response["message"].startswith("We found your size 42! Please check stock in a specific store")
    assert "Found 2 products" in response["message"]
    assert response["data"]["results"]["site_search_url"] == \
        "https://topsport.ge/en/products?term=nike&search_type=name"


def test_no_size_note_for_alternatives_and_need_size():
    alternatives = _context(detected_size="42", matched_by="size_alternatives")
    need_size = _context(query="pegasus", result_mode="need_size", model_hint="pegasus", detected_size=None)
    for context in (alternatives, need_size):
        message = build_response(context, user_id="u", response_type="product_search", locale="en")["message"]
        assert "We found your size" not in message