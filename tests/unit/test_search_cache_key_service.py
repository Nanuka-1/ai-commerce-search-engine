from app.services.search_cache_key_service import build_search_cache_key


def test_same_search_params_produce_same_cache_key():
    first_key = build_search_cache_key(
        normalized_query="nike air max",
        detected_brand="nike",
        size="42",
        category="men",
        style_group="lifestyle_sneakers",
        strategy_name="model_search",
        limit=5,
        offset=0,
    )

    second_key = build_search_cache_key(
        normalized_query="nike air max",
        detected_brand="nike",
        size="42",
        category="men",
        style_group="lifestyle_sneakers",
        strategy_name="model_search",
        limit=5,
        offset=0,
    )

    assert first_key == second_key


def test_different_size_produces_different_cache_key():
    size_42_key = build_search_cache_key(
        normalized_query="nike air max",
        detected_brand="nike",
        size="42",
        category="men",
        style_group="lifestyle_sneakers",
        strategy_name="model_search",
        limit=5,
        offset=0,
    )

    size_43_key = build_search_cache_key(
        normalized_query="nike air max",
        detected_brand="nike",
        size="43",
        category="men",
        style_group="lifestyle_sneakers",
        strategy_name="model_search",
        limit=5,
        offset=0,
    )

    assert size_42_key != size_43_key


def test_different_strategy_produces_different_cache_key():
    model_key = build_search_cache_key(
        normalized_query="nike air max",
        detected_brand="nike",
        size="42",
        category="men",
        style_group="lifestyle_sneakers",
        strategy_name="model_search",
        limit=5,
        offset=0,
    )

    brand_size_key = build_search_cache_key(
        normalized_query="nike air max",
        detected_brand="nike",
        size="42",
        category="men",
        style_group="lifestyle_sneakers",
        strategy_name="brand_size",
        limit=5,
        offset=0,
    )

    assert model_key != brand_size_key


def test_pagination_changes_cache_key():
    first_page_key = build_search_cache_key(
        normalized_query="nike air max",
        detected_brand="nike",
        size="42",
        category="men",
        style_group="lifestyle_sneakers",
        strategy_name="model_search",
        limit=5,
        offset=0,
    )

    second_page_key = build_search_cache_key(
        normalized_query="nike air max",
        detected_brand="nike",
        size="42",
        category="men",
        style_group="lifestyle_sneakers",
        strategy_name="model_search",
        limit=5,
        offset=5,
    )

    assert first_page_key != second_page_key


def test_cache_key_contains_main_search_parts():
    key = build_search_cache_key(
        normalized_query="nike air max",
        detected_brand="nike",
        size="42",
        category="men",
        style_group="lifestyle_sneakers",
        strategy_name="model_search",
        limit=5,
        offset=0,
    )

    assert "nike air max" in key
    assert "brand=nike" in key
    assert "size=42" in key
    assert "category=men" in key
    assert "style_group=lifestyle_sneakers" in key
    assert "strategy=model_search" in key
    assert "limit=5" in key
    assert "offset=0" in key