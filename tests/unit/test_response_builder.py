import pytest
from types import SimpleNamespace
from app.services.response_builder import build_response, AVAILABILITY_CTA
from app.schemas.search_context import SearchContext
from app.services.response_builder import NO_SIZE_NOTE_KEYS
from app.services.response_builder import georgian_genitive


def make_product(product_id: int, product_url: str | None = None, is_active: bool = True):
    return SimpleNamespace(
        id=product_id,
        sku=f"SKU-{product_id}",
        name=f"Product {product_id}",
        price=100.0,
        product_url=product_url or f"https://topsport.ge/product/sku-{product_id}",
        is_active=is_active,
    )


def test_pagination_first_page():
    context = SearchContext(
        query="nike",
        normalized_query="nike",
        matched_by="query",
        items=[
            make_product(1),
            make_product(2),
            make_product(3),
            make_product(4),
            make_product(5),
        ],
        total_count=14,
        limit=5,
        offset=0,
    )

    response = build_response(context, user_id="test_user", response_type="product_search")

    results = response["data"]["results"]

    assert results["has_more"] is True
    assert results["next_offset"] == 5


def test_pagination_middle_page():
    context = SearchContext(
        query="nike",
        normalized_query="nike",
        matched_by="query",
        items=[
            make_product(6),
            make_product(7),
            make_product(8),
            make_product(9),
            make_product(10),
        ],
        total_count=14,
        limit=5,
        offset=5,
    )

    response = build_response(context, user_id="test_user", response_type="product_search")

    results = response["data"]["results"]

    assert results["shown"] == 5
    assert results["has_more"] is True
    assert results["next_offset"] == 10



def test_pagination_last_page():
    context = SearchContext(
        query="nike",
        normalized_query="nike",
        matched_by="query",
        items=[
            make_product(11),
            make_product(12),
            make_product(13),
            make_product(14),
        ],
        total_count=14,
            limit=5,
            offset=10,
    )

    response = build_response(context, user_id="test_user", response_type="product_search")

    results = response["data"]["results"]

    assert results["shown"] == 4
    assert results["has_more"] is False
    assert results["next_offset"] is None

def test_empty_results():
    context = SearchContext(
        query="unknown product",
        normalized_query="unknown product",
        matched_by="query",
        items=[],
        total_count=0,
        limit=5,
        offset=0,
    )

    response = build_response(context, user_id="test_user", response_type="product_search")

    results = response["data"]["results"]

    assert results["shown"] == 0
    assert results["has_more"] is False
    assert results["next_offset"] is None


def test_empty_results_has_message():
    context = SearchContext(
        query="unknown product",
        normalized_query="unknown product",
        matched_by="query",
        items=[],
        total_count=0,
        limit=5,
        offset=0,
    )

    response = build_response(context, user_id="test_user", response_type="product_search")

    assert "message" in response
    assert response["message"] is not None
    assert response["message"].strip() != ""

def test_serialized_items_include_url_and_availability():
    context = SearchContext(
        query="nike",
        normalized_query="nike",
        matched_by="query",
        items=[
            make_product(1, product_url="https://topsport.ge/product/nike-air-max", is_active=True),
            make_product(2, is_active=False),
        ],
        total_count=2,
        limit=5,
        offset=0,
    )

    response = build_response(context, user_id="test_user", response_type="product_search")

    items = response["data"]["results"]["items"]

    assert items[0]["product_url"] == "https://topsport.ge/product/nike-air-max"
    assert items[0]["available"] is True
    assert items[1]["available"] is False

def test_availability_cta_added_in_english_for_latin_query():
    context = SearchContext(
        query="nike",
        normalized_query="nike",
        matched_by="query",
        items=[make_product(1)],
        total_count=1,
        limit=5,
        offset=0,
    )

    response = build_response(context, user_id="test_user", response_type="product_search", locale="en")

    assert AVAILABILITY_CTA["en"] in response["message"]


def test_availability_cta_added_in_georgian_for_georgian_query():
    context = SearchContext(
        query="ნაიკი",
        normalized_query="ნაიკი",
        matched_by="query",
        items=[make_product(1)],
        total_count=1,
        limit=5,
        offset=0,
    )

    response = build_response(context, user_id="test_user", response_type="product_search")

    assert AVAILABILITY_CTA["ka"] in response["message"]


def test_no_cta_when_no_products_found():
    context = SearchContext(
        query="unknown product",
        normalized_query="unknown product",
        matched_by="query",
        items=[],
        total_count=0,
        limit=5,
        offset=0,
    )

    response = build_response(context, user_id="test_user", response_type="product_search")

    assert AVAILABILITY_CTA["en"] not in response["message"]

def test_availability_cta_uses_georgian_when_query_mixes_georgian_and_latin_brand_name():
    context = SearchContext(
        query="მინდა Nike-ის სპორტული ფეხსაცმელი",
        normalized_query="მინდა nike-ის სპორტული ფეხსაცმელი",
        matched_by="query",
        items=[make_product(1)],
        total_count=1,
        limit=5,
        offset=0,
    )

    response = build_response(context, user_id="test_user", response_type="product_search")

    assert AVAILABILITY_CTA["ka"] in response["message"]


from app.services.translations import TRANSLATIONS, resolve_language


def make_context(**overrides):
    values = dict(query="nike", normalized_query="nike", matched_by="query",
                  items=[make_product(1), make_product(2)], total_count=2, limit=5, offset=0)
    values.update(overrides)
    return SearchContext(**values)


def test_all_search_messages_exist_in_both_languages():
    en_keys = {k for k in TRANSLATIONS["en"] if k.startswith("search_")}
    ka_keys = {k for k in TRANSLATIONS["ka"] if k.startswith("search_")}
    assert en_keys == ka_keys


def test_all_translation_keys_exist_in_both_languages():
    assert set(TRANSLATIONS["en"]) == set(TRANSLATIONS["ka"])


def test_georgian_query_gets_fully_georgian_answer():
    response = build_response(make_context(query="ნაიკი", normalized_query="ნაიკი"),
                              user_id="u", response_type="product_search", locale="en")
    assert response["message"].startswith("ვიპოვე 2 პროდუქტი")


def test_latin_query_follows_site_locale():
    ka = build_response(make_context(), user_id="u", response_type="product_search", locale="ka")
    en = build_response(make_context(), user_id="u", response_type="product_search", locale="en")
    assert ka["message"].startswith("ვიპოვე 2 პროდუქტი")
    assert en["message"].startswith("Found 2 products")


def test_color_does_not_override_need_size():
    context = make_context(query="nike pegasus black", result_mode="need_size",
                           model_hint="pegasus", detected_color="black")
    message = build_response(context, user_id="u", response_type="product_search", locale="en")["message"]
    assert "specify the size" in message
    assert "black" in message


def test_color_matched_note_when_item_has_color():
    item = make_product(1)
    item.color = "black"
    context = make_context(items=[item], total_count=1, detected_color="black")
    message = build_response(context, user_id="u", response_type="product_search", locale="en")["message"]
    assert "Showing black options first" in message


def test_brand_fallback_message_is_shown():
    context = make_context(query="nike zoomx", matched_by="brand_fallback")
    message = build_response(context, user_id="u", response_type="product_search", locale="en")["message"]
    assert "Exact match for 'nike zoomx' was not found" in message


def test_no_products_message_in_georgian():
    context = make_context(query="ნაიკი", items=[], total_count=0)
    message = build_response(context, user_id="u", response_type="product_search")["message"]
    assert message.startswith(TRANSLATIONS["ka"]["search_no_products"])
    # 13.10: ссылку на поиск сайта в текст не ставим — сайт ищет фразу целиком и часто показывает 0 товаров
    assert "https://" not in message


@pytest.mark.parametrize("text, locale, expected", [
    ("ნაიკი 42", "en", "ka"),
    ("მინდა nike", "en", "ka"),
    ("nike 42", "en", "en"),
    ("nike 42", "ka", "ka"),
    ("CW2288-111", None, "ka"),
    ("nike 42", "fr", "ka"),
    (None, "en", "en"),
])
def test_resolve_language(text, locale, expected):
    assert resolve_language(text, locale) == expected

@pytest.mark.parametrize("language", ["en", "ka"])
@pytest.mark.parametrize("overrides, key", [
    ({"result_mode": "need_size"}, "search_need_size"),
    ({"result_mode": "need_model", "items": [make_product(1)], "total_count": 1}, "search_need_model_one"),
    ({"result_mode": "need_model"}, "search_need_model_many"),
    ({"matched_by": "size_alternatives"}, "search_size_alternatives"),
    ({"matched_by": "brand_fallback"}, "search_brand_fallback"),
    ({"result_mode": "exact_model_match"}, "search_exact_model"),
    ({"result_mode": "fallback_similar"}, "search_similar_model"),
    ({"result_mode": "broad_query"}, "search_broad_query"),
    ({"items": [make_product(1)], "total_count": 1}, "search_found_one"),
    ({}, "search_found_many"),
])
def test_every_response_branch_in_both_languages(overrides, key, language):
    context = make_context(model_hint="pegasus", detected_size="42", **overrides)

    message = build_response(context, user_id="u", response_type="product_search", locale=language)["message"]

    expected = TRANSLATIONS[language][key].format(
        query=context.query, model="pegasus", size="42", color=None,
        total=context.total_count, shown=len(context.items),
        model_gen=georgian_genitive("pegasus"),  # 13.10: «Pegasus-ის» — грузинский падеж модели
    )
    assert expected in message
    size_note = TRANSLATIONS[language]["search_size_available"].format(size="42")
    if key in NO_SIZE_NOTE_KEYS:
        assert size_note not in message  # альтернативы / вопрос о размере — без "нашли размер"
    else:
        assert message.startswith(size_note)  # размер найден — говорим первым делом
    assert message.endswith(AVAILABILITY_CTA[language])