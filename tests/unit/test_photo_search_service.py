"""29.10 (поиск по фото, шаг 2): честный вердикт, проверка фото, разбор ответа ИИ, SQL. Без Gemini и базы."""
import pytest

from app.services.photo_search_service import (
    EXACT, JUNK, NOT_FOUND, SIMILAR,
    build_photo_sql, check_photo, decide, parse_photo_understanding,
)

PRODUCT = {"is_product": True, "product_type": "footwear", "brand": "Adidas", "model_text": "SAMBA", "color": "cream"}


@pytest.mark.parametrize("pages, expected", [
    ([("samba-og-w-1", 0.870), ("other", 0.845)], EXACT),      # замер 29.10: samba1 — своя модель, разрыв 0.025
    ([("samba-og-w-1", 0.840), ("other", 0.818)], EXACT),      # samba2 — разрыв 0.022
    ([("a", 0.86), ("b", 0.855)], SIMILAR),                    # высоко, но почти поровну — не утверждаем «точно»
    ([("a", 0.707), ("b", 0.704)], SIMILAR),                   # белая Samba — похожие
    ([("a", 0.653), ("b", 0.644)], NOT_FOUND),                 # низко — похожего нет
    ([], NOT_FOUND),
])
def test_decide_by_numbers(pages, expected):
    assert decide(pages, PRODUCT) == expected


def test_not_a_product_is_junk_even_if_something_looks_similar():
    assert decide([("a", 0.9), ("b", 0.7)], {**PRODUCT, "is_product": False}) == JUNK


def test_without_ai_description_numbers_decide():
    assert decide([("a", 0.87), ("b", 0.84)], None) == EXACT


def test_check_photo():
    assert check_photo(b"x", "image/jpeg") is None
    assert check_photo(b"x", "image/gif") == "photo_bad_format"
    assert check_photo(b"x" * (5 * 1024 * 1024 + 1), "image/png") == "photo_too_big"
    assert check_photo(b"", "image/png") == "photo_too_big"


def test_parse_photo_understanding():
    raw = '```json\n{"is_product": true, "product_type": "footwear", "brand": "Adidas", "model_text": "SAMBA", "color": "cream"}\n```'
    assert parse_photo_understanding(raw) == PRODUCT
    assert parse_photo_understanding('{"is_product": "yes"}') is None          # не bool — не верим
    assert parse_photo_understanding("not json") is None
    assert parse_photo_understanding('{"is_product": false, "product_type": "car"}')["product_type"] is None


def test_sql_filters_only_what_ai_saw():
    sql, params = build_photo_sql("ფეხსაცმ", "Adidas", 20)
    assert "product_image_embeddings" in sql and params["brand"] == "adidas"
    assert params["category_like"] == "%ფეხსაცმ%"
    sql, params = build_photo_sql(None, None, 20)
    assert "brand" not in params and "category_like" not in params