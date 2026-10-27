from types import SimpleNamespace

from app.services.product_ranking_service import (
    score_product,
    rank_products,
    tokenize_query,
)


def make_product(
    name: str,
    brand: str,
    sku: str = "SKU-1",
    size: str | None = None,
    category_slug: str | None = None,
    style_group: str | None = None,
    color: str | None = None,  # <-- new
):
    return SimpleNamespace(
        name=name,
        brand=brand,
        sku=sku,
        size=size,
        category_slug=category_slug,
        style_group=style_group,
        color=color,  # <-- new
    )


def test_tokenize_query_splits_by_spaces():
    assert tokenize_query("nike air max") == ["nike", "air", "max"]


def test_brand_match_scores_higher_than_unrelated_product():
    nike = make_product("Nike Air Max", brand="nike")
    adidas = make_product("Adidas Runner", brand="adidas")

    tokens = tokenize_query("nike")

    assert score_product(
        product=nike,
        tokens=tokens,
        normalized_query="nike",
        usage_type=None,
        model_hint=None,
    ) > score_product(
        product=adidas,
        tokens=tokens,
        normalized_query="nike",
        usage_type=None,
        model_hint=None,
    )


def test_rank_products_puts_relevant_brand_first():
    products = [
        make_product("Adidas Runner", brand="adidas"),
        make_product("Nike Air Max", brand="nike"),
    ]

    ranked = rank_products(
        products=products,
        tokens=tokenize_query("nike"),
        normalized_query="nike",
        usage_type=None,
        model_hint=None,
    )

    assert ranked[0].brand == "nike"

def test_brand_and_model_should_beat_size_only_match():
    nike_air_max_wrong_size = make_product(
        name="Nike Air Max",
        brand="nike",
        size="41",
    )

    puma_correct_size = make_product(
        name="Puma Runner",
        brand="puma",
        size="42",
    )

    ranked = rank_products(
        products=[
            puma_correct_size,
            nike_air_max_wrong_size,
        ],
        tokens=tokenize_query("nike air max 42"),
        normalized_query="nike air max 42",
        usage_type=None,
        model_hint="air max",
        requested_size="42",
    )

    assert ranked[0].brand == "nike"
    assert ranked[0].name == "Nike Air Max"

def test_sku_match_ranks_first():
    exact_sku = make_product(
        name="Basic Product",
        brand="unknown",
        sku="AB-123",
    )

    nike_product = make_product(
        name="Nike Air Max",
        brand="nike",
        sku="NK-999",
    )

    ranked = rank_products(
        products=[
            nike_product,
            exact_sku,
        ],
        tokens=tokenize_query("AB-123"),
        normalized_query="ab-123",
        usage_type=None,
        model_hint=None,
    )

    assert ranked[0].sku == "AB-123"

def test_correct_size_wins_between_same_model():
    wrong_size = make_product(
        name="Nike Air Max",
        brand="nike",
        size="41",
    )

    correct_size = make_product(
        name="Nike Air Max",
        brand="nike",
        size="42",
    )

    ranked = rank_products(
        products=[
            wrong_size,
            correct_size,
        ],
        tokens=tokenize_query("nike air max 42"),
        normalized_query="nike air max 42",
        usage_type=None,
        model_hint="air max",
        requested_size="42",
    )

    assert ranked[0].size == "42"

def test_requested_style_group_boosts_matching_product():
    casual = make_product(
        name="Nike Lifestyle Sneaker",
        brand="nike",
        style_group="lifestyle_sneakers",
    )

    running = make_product(
        name="Nike Running Shoe",
        brand="nike",
        style_group="running_shoes",
    )

    ranked = rank_products(
        products=[
            casual,
            running,
        ],
        tokens=tokenize_query("nike"),
        normalized_query="nike",
        usage_type=None,
        model_hint=None,
        requested_style_group="running_shoes",
    )

    assert ranked[0].style_group == "running_shoes"

def test_requested_color_boosts_matching_product_but_keeps_others():
    black = make_product(
        name="Nike Air Max",
        brand="nike",
        color="black",
    )

    no_color_data = make_product(
        name="Nike Air Max",
        brand="nike",
        color=None,
    )

    ranked = rank_products(
        products=[
            no_color_data,
            black,
        ],
        tokens=tokenize_query("nike air max"),
        normalized_query="nike air max",
        usage_type=None,
        model_hint=None,
        requested_color="black",
    )

    assert ranked[0].color == "black"
    assert len(ranked) == 2

def test_score_product_applies_basketball_synonym_bonus_for_georgian_text():
    product = SimpleNamespace(
        name="Under Armour მამაკაცის კალათბურთის ფეხსაცმელი",
        brand="Under Armour",
        sku="UA-1234-42",
        size="42",
        category_slug=None,
        style_group=None,
        color=None,
    )

    score_with_usage_type = score_product(
        product=product,
        tokens=[],
        normalized_query="",
        usage_type="basketball",
        model_hint=None,
    )
    score_without_usage_type = score_product(
        product=product,
        tokens=[],
        normalized_query="",
        usage_type=None,
        model_hint=None,
    )

    assert score_with_usage_type == score_without_usage_type + 15
