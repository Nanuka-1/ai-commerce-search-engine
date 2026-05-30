from app.services.search_strategy_service import choose_search_strategy


def test_choose_broad_search_for_brand_only():
    strategy = choose_search_strategy(
        raw_query="nike",
        brand="nike",
        size=None,
        model_hint=None,
        is_sku=False,
    )

    assert strategy.value == "broad_search"


def test_choose_brand_size_when_brand_and_size_exist():
    strategy = choose_search_strategy(
        raw_query="nike women 39",
        brand="nike",
        size="39",
        model_hint=None,
        is_sku=False,
    )

    assert strategy.value == "brand_size"


def test_choose_model_search_when_model_hint_exists():
    strategy = choose_search_strategy(
        raw_query="nike air max 39",
        brand="nike",
        size="39",
        model_hint="air max",
        is_sku=False,
    )

    assert strategy.value == "model_search"


def test_choose_exact_sku_has_highest_priority():
    strategy = choose_search_strategy(
        raw_query="ABC123",
        brand="nike",
        size="39",
        model_hint="air max",
        is_sku=True,
    )

    assert strategy.value == "exact_sku"