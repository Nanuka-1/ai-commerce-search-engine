from types import SimpleNamespace

from app.schemas.search_request import SearchRequest
from app.schemas.search_context import SearchContext
from app.services import product_service
from app.services import product_fallback_service


def make_product(
    product_id,
    name,
    brand="nike",
    sku="SKU-1",
    price=100.0,
    size=None,
    category_slug=None,
    style_group=None,
):
    return SimpleNamespace(
        id=product_id,
        name=name,
        brand=brand,
        sku=sku,
        price=price,
        size=size,
        category_slug=category_slug,
        style_group=style_group,
    )


def test_search_products_returns_search_context(monkeypatch):
    products = [
        make_product(1, "Nike Air Max"),
        make_product(2, "Nike Runner"),
    ]

    def fake_get_products_by_query(
        db,
        q,
        size=None,
        category=None,
        style_group=None,
        brand=None,
        limit=5,
        offset=0,
    ):
        return products, len(products)

    monkeypatch.setattr(
        product_service,
        "get_products_by_query",
        fake_get_products_by_query,
    )

    monkeypatch.setattr(product_service.cache_service, "get", lambda key: None)
    monkeypatch.setattr(product_service.cache_service, "set", lambda key, value, ttl=60: None)

    request = SearchRequest(
        raw_query="nike",
        size=None,
        category=None,
        limit=5,
        offset=0,
    )

    result = product_service.search_products(db=None, request=request)

    assert isinstance(result, SearchContext)
    assert result.query == "nike"
    assert result.total_count == 2
    assert len(result.items) == 2


def test_search_products_ranks_relevant_product_first(monkeypatch):
    products = [
        make_product(1, "Adidas Runner", brand="adidas", sku="AD-1"),
        make_product(2, "Nike Air Max", brand="nike", sku="NK-1"),
    ]

    def fake_get_products_by_query(
        db,
        q,
        size=None,
        category=None,
        style_group=None,
        brand=None,
        limit=5,
        offset=0,
    ):
        return products, len(products)

    monkeypatch.setattr(
        product_service,
        "get_products_by_query",
        fake_get_products_by_query,
    )

    monkeypatch.setattr(product_service.cache_service, "get", lambda key: None)
    monkeypatch.setattr(product_service.cache_service, "set", lambda key, value, ttl=60: None)

    request = SearchRequest(
        raw_query="nike",
        limit=5,
        offset=0,
    )

    result = product_service.search_products(db=None, request=request)

    assert result.items[0]["brand"] == "nike"
    assert result.items[0]["name"] == "Nike Air Max"


def test_search_products_pagination(monkeypatch):
    products = [
        make_product(i, f"Nike Product {i}", brand="nike")
        for i in range(1, 11)
    ]

    def fake_get_products_by_query(
        db,
        q,
        size=None,
        category=None,
        style_group=None,
        brand=None,
        limit=5,
        offset=0,
    ):
        return products, len(products)

    monkeypatch.setattr(
        product_service,
        "get_products_by_query",
        fake_get_products_by_query,
    )

    monkeypatch.setattr(product_service.cache_service, "get", lambda key: None)
    monkeypatch.setattr(product_service.cache_service, "set", lambda key, value, ttl=60: None)

    request = SearchRequest(
        raw_query="nike",
        limit=5,
        offset=5,
    )

    result = product_service.search_products(db=None, request=request)

    assert len(result.items) == 5
    assert result.items[0]["id"] == 6


def test_search_products_returns_cached_context(monkeypatch):
    cached_context = SearchContext(
        query="nike",
        normalized_query="nike",
        matched_by="query",
        items=[],
        total_count=0,
        limit=5,
        offset=0,
    )

    def fake_cache_get(key):
        return cached_context

    def fake_get_products_by_query(*args, **kwargs):
        raise AssertionError("Repository should not be called on cache hit")

    monkeypatch.setattr(product_service.cache_service, "get", fake_cache_get)
    monkeypatch.setattr(
        product_service,
        "get_products_by_query",
        fake_get_products_by_query,
    )

    request = SearchRequest(
        raw_query="nike",
        limit=5,
        offset=0,
    )

    result = product_service.search_products(db=None, request=request)

    assert result is cached_context


def test_search_products_empty_result(monkeypatch):
    def fake_get_products_by_query(*args, **kwargs):
        return [], 0

    monkeypatch.setattr(
        product_service,
        "get_products_by_query",
        fake_get_products_by_query,
    )

    monkeypatch.setattr(product_service.cache_service, "get", lambda key: None)
    monkeypatch.setattr(product_service.cache_service, "set", lambda *args, **kwargs: None)

    request = SearchRequest(
        raw_query="unknown",
        limit=5,
        offset=0,
    )

    result = product_service.search_products(db=None, request=request)

    assert result.items == []
    assert result.total_count == 0

def test_search_products_brand_fallback(monkeypatch):
    products = [
        make_product(
            1,
            "Adidas Ultraboost",
            brand="adidas",
            sku="AD-1",
        ),
    ]

    call_count = {"count": 0}

    def fake_get_products_by_query(
        db,
        q,
        size=None,
        category=None,
        style_group=None,
        brand=None,
        limit=200,
        offset=0,
    ):
        call_count["count"] += 1

        # первый поиск ничего не нашёл
        if call_count["count"] == 1:
            return [], 0

        # fallback по бренду нашёл товар
        return products, len(products)

    monkeypatch.setattr(
        product_service,
        "get_products_by_query",
        fake_get_products_by_query,
    )

    monkeypatch.setattr(
        product_service.cache_service,
        "get",
        lambda key: None,
    )

    monkeypatch.setattr(
        product_service.cache_service,
        "set",
        lambda *args, **kwargs: None,
    )

    request = SearchRequest(
        raw_query="adidas running",
        limit=5,
        offset=0,
    )

    result = product_service.search_products(
        db=None,
        request=request,
    )

    assert result.matched_by == "brand_fallback"
    assert result.total_count == 1
    assert result.items[0]["brand"] == "adidas"

def test_get_product_by_sku_service_fallback_parsing(monkeypatch):
    product = make_product(
        1,
        "Nike Air Max",
        brand="nike",
        sku="NK-123",
        size=42,
    )

    call_count = {"count": 0}

    def fake_get_product_by_sku(db, sku):
        call_count["count"] += 1

        # первый поиск по полному SKU ничего не находит
        if sku == "NK-123-42":
            return None

        # fallback по базовому SKU находит товар
        if sku == "NK-123":
            return product

        return None

    monkeypatch.setattr(
        product_service,
        "get_product_by_sku",
        fake_get_product_by_sku,
    )

    monkeypatch.setattr(
        product_service.cache_service,
        "get",
        lambda key: None,
    )

    monkeypatch.setattr(
        product_service.cache_service,
        "set",
        lambda *args, **kwargs: None,
    )

    result = product_service.get_product_by_sku_service(
        db=None,
        sku="NK-123-42",
    )

    assert result.matched_by == "sku"
    assert result.base_sku == "NK-123"
    assert result.detected_size == "42"
    assert result.total_count == 1
    assert result.items[0]["sku"] == "NK-123"


def test_model_search_ranks_exact_model_first(monkeypatch):
        products = [
        make_product(1, "Adidas Predator", brand="adidas", sku="AD-1"),
        make_product(2, "Nike Air Max 90", brand="nike", sku="NK-AIRMAX"),
        ]

        def fake_get_products_by_query(
                db,
                q,
                size=None,
                category=None,
                style_group=None,
                brand=None,
                limit=200,
                offset=0,
        ):
            return products, len(products)

        monkeypatch.setattr(
            product_service,
            "get_products_by_query",
            fake_get_products_by_query,
        )

        monkeypatch.setattr(product_service.cache_service, "get", lambda key: None)
        monkeypatch.setattr(product_service.cache_service, "set", lambda *args, **kwargs: None)

        request = SearchRequest(
            raw_query="nike air max",
            brand="nike",
            limit=5,
            offset=0,
        )

        result = product_service.search_products(db=None, request=request)

        assert result.search_strategy == "model_search"
        assert result.items[0]["brand"] == "nike"
        assert result.items[0]["sku"] == "NK-AIRMAX"

def test_model_search_sets_fallback_metadata_when_exact_model_not_found(monkeypatch):
    fallback_products = [
        make_product(
            1,
            "Nike Runner",
            brand="nike",
            sku="NK-RUN-44",
            size="44",
        ),
    ]

    def fake_get_products_by_query(
        db,
        q,
        size=None,
        category=None,
        style_group=None,
        brand=None,
        limit=200,
        offset=0,
    ):
        return [], 0

    def fake_search_same_brand_size_products(
        db,
        brand,
        size=None,
        category=None,
        style_group=None,
        limit=200,
    ):
        return fallback_products, len(fallback_products)

    monkeypatch.setattr(
        product_service,
        "get_products_by_query",
        fake_get_products_by_query,
    )

    monkeypatch.setattr(
        product_fallback_service,
        "search_same_brand_size_products",
        fake_search_same_brand_size_products,
    )

    monkeypatch.setattr(product_service.cache_service, "get", lambda key: None)
    monkeypatch.setattr(product_service.cache_service, "set", lambda *args, **kwargs: None)

    request = SearchRequest(
        raw_query="nike air max 44",
        brand="nike",
        size="44",
        limit=5,
        offset=0,
    )

    result = product_service.search_products(
        db=None,
        request=request,
    )

    assert result.search_strategy == "model_search"
    assert result.matched_by == "similar_model_same_brand_size"
    assert result.retrieval_mode == "keyword"
    assert result.fallback_level == "same_brand_same_size"
    assert result.alternative_reason == "exact_model_not_found"
    assert result.total_count == 1
    assert result.items[0]["brand"] == "nike"
    assert result.items[0]["size"] == "44"

def test_model_search_stops_at_same_brand_same_size_fallback(monkeypatch):
    fallback_products = [
        make_product(
            1,
            "Nike Runner",
            brand="nike",
            sku="NK-RUN-44",
            size="44",
        ),
    ]

    call_tracker = {
        "same_brand_size_called": False,
    }

    def fake_get_products_by_query(
        db,
        q,
        size=None,
        category=None,
        style_group=None,
        brand=None,
        limit=200,
        offset=0,
    ):
        return [], 0

    def fake_search_same_brand_size_products(
        db,
        brand,
        size=None,
        category=None,
        style_group=None,
        limit=200,
    ):
        call_tracker["same_brand_size_called"] = True
        return fallback_products, len(fallback_products)

    monkeypatch.setattr(
        product_service,
        "get_products_by_query",
        fake_get_products_by_query,
    )

    monkeypatch.setattr(
        product_fallback_service,
        "search_same_brand_size_products",
        fake_search_same_brand_size_products,
    )

    monkeypatch.setattr(product_service.cache_service, "get", lambda key: None)
    monkeypatch.setattr(product_service.cache_service, "set", lambda *args, **kwargs: None)

    request = SearchRequest(
        raw_query="nike air max 44",
        brand="nike",
        size="44",
        limit=5,
        offset=0,
    )

    result = product_service.search_products(
        db=None,
        request=request,
    )

    assert call_tracker["same_brand_size_called"] is True

    assert result.search_strategy == "model_search"
    assert result.matched_by == "similar_model_same_brand_size"
    assert result.fallback_level == "same_brand_same_size"
    assert result.alternative_reason == "exact_model_not_found"
    assert result.total_count == 1


def test_model_search_falls_back_to_same_category_same_size(monkeypatch):
    category_products = [
        make_product(
            1,
            "Adidas Runner",
            brand="adidas",
            sku="AD-RUN-44",
            size="44",
        ),
    ]

    def fake_get_products_by_query(
        db,
        q,
        size=None,
        category=None,
        style_group=None,
        brand=None,
        limit=200,
        offset=0,
    ):
        return [], 0

    def fake_search_same_brand_size_products(
        db,
        brand,
        size=None,
        category=None,
        style_group=None,
        limit=200,
    ):
        return [], 0

    def fake_get_products_by_size(
        db,
        size,
        category=None,
        limit=200,
    ):
        if category == "qalis-fekhsatsmeli":
            return category_products, len(category_products)

        return [], 0

    monkeypatch.setattr(
        product_service,
        "get_products_by_query",
        fake_get_products_by_query,
    )

    monkeypatch.setattr(
        product_fallback_service,
        "search_same_brand_size_products",
        fake_search_same_brand_size_products,
    )

    monkeypatch.setattr(
        product_fallback_service,
        "get_products_by_size",
        fake_get_products_by_size,
    )

    monkeypatch.setattr(product_service.cache_service, "get", lambda key: None)
    monkeypatch.setattr(product_service.cache_service, "set", lambda *args, **kwargs: None)

    request = SearchRequest(
        raw_query="nike air max 44",
        brand="nike",
        size="44",
        category="qalis-fekhsatsmeli",
        limit=5,
        offset=0,
    )

    result = product_service.search_products(
        db=None,
        request=request,
    )

    assert result.search_strategy == "model_search"
    assert result.matched_by == "same_category_same_size"
    assert result.retrieval_mode == "keyword"
    assert result.fallback_level == "same_category_same_size"
    assert result.alternative_reason == "same_brand_not_found"
    assert result.total_count == 1
    assert result.items[0]["brand"] == "adidas"
    assert result.items[0]["size"] == "44"

def test_model_search_falls_back_to_same_size(monkeypatch):
    size_products = [
        make_product(
            1,
            "Puma Runner",
            brand="puma",
            sku="PM-RUN-44",
            size="44",
        ),
    ]

    def fake_get_products_by_query(
        db,
        q,
        size=None,
        category=None,
        style_group=None,
        brand=None,
        limit=200,
        offset=0,
    ):
        return [], 0

    def fake_search_same_brand_size_products(
        db,
        brand,
        size=None,
        category=None,
        style_group=None,
        limit=200,
    ):
        return [], 0

    def fake_get_products_by_size(
        db,
        size,
        category=None,
        limit=200,
    ):
        if category is None:
            return size_products, len(size_products)

        return [], 0

    monkeypatch.setattr(
        product_service,
        "get_products_by_query",
        fake_get_products_by_query,
    )

    monkeypatch.setattr(
        product_fallback_service,
        "search_same_brand_size_products",
        fake_search_same_brand_size_products,
    )

    monkeypatch.setattr(
        product_fallback_service,
        "get_products_by_size",
        fake_get_products_by_size,
    )

    monkeypatch.setattr(product_service.cache_service, "get", lambda key: None)
    monkeypatch.setattr(product_service.cache_service, "set", lambda *args, **kwargs: None)

    request = SearchRequest(
        raw_query="nike air max 44",
        brand="nike",
        size="44",
        category="qalis-fekhsatsmeli",
        limit=5,
        offset=0,
    )

    result = product_service.search_products(
        db=None,
        request=request,
    )

    assert result.search_strategy == "model_search"
    assert result.matched_by == "same_size"
    assert result.retrieval_mode == "keyword"
    assert result.fallback_level == "same_size"
    assert result.alternative_reason == "same_category_not_found"
    assert result.total_count == 1
    assert result.items[0]["brand"] == "puma"
    assert result.items[0]["size"] == "44"

def test_model_search_returns_no_results_when_all_fallbacks_fail(monkeypatch):

    def fake_get_products_by_query(
        db,
        q,
        size=None,
        category=None,
        style_group=None,
        brand=None,
        limit=200,
        offset=0,
    ):
        return [], 0

    def fake_search_same_brand_size_products(
        db,
        brand,
        size=None,
        category=None,
        style_group=None,
        limit=200,
    ):
        return [], 0

    def fake_get_products_by_size(
        db,
        size,
        category=None,
        limit=200,
    ):
        return [], 0

    monkeypatch.setattr(
        product_service,
        "get_products_by_query",
        fake_get_products_by_query,
    )

    monkeypatch.setattr(
        product_fallback_service,
        "search_same_brand_size_products",
        fake_search_same_brand_size_products,
    )

    monkeypatch.setattr(
        product_fallback_service,
        "get_products_by_size",
        fake_get_products_by_size,
    )

    request = SearchRequest(
        raw_query="nike air max 44",
        brand="nike",
        size="44",
        category="qalis-fekhsatsmeli",
        limit=5,
        offset=0,
    )

    result = product_service.search_products(
        db=None,
        request=request,
    )

    assert result.search_strategy == "model_search"
    assert result.matched_by == "no_results"
    assert result.retrieval_mode == "keyword"
    assert result.fallback_level == "no_results"
    assert result.alternative_reason == "no_fallback_results"

    assert result.total_count == 0
    assert result.items == []

def test_broad_search_boosts_matching_color(monkeypatch):
    products = [
        make_product(1, "Nike Runner Black", brand="nike", sku="NK-BLACK"),
        make_product(2, "Nike Runner Red", brand="nike", sku="NK-RED"),
    ]
    products[0].color = "black"
    products[1].color = "red"

    def fake_get_products_by_query(
        db,
        q,
        size=None,
        category=None,
        style_group=None,
        brand=None,
        limit=50,
        offset=0,
    ):
        return products, len(products)

    monkeypatch.setattr(
        product_service,
        "get_products_by_query",
        fake_get_products_by_query,
    )

    monkeypatch.setattr(product_service.cache_service, "get", lambda key: None)
    monkeypatch.setattr(product_service.cache_service, "set", lambda *args, **kwargs: None)

    request = SearchRequest(
        raw_query="nike",
        color="red",
        limit=5,
        offset=0,
    )

    result = product_service.search_products(db=None, request=request)

    assert result.search_strategy == "broad_search"
    assert result.items[0]["sku"] == "NK-RED"


def assert_search_context_contract(context: SearchContext):
    required_fields = [
        "query",
        "normalized_query",
        "matched_by",
        "search_strategy",
        "retrieval_mode",
        "fallback_level",
        "alternative_reason",
        "items",
        "total_count",
        "limit",
        "offset",
    ]

    for field in required_fields:
        assert hasattr(context, field), f"Missing SearchContext field: {field}"

    assert context.retrieval_mode is not None, "retrieval_mode must be set"
    assert context.items is not None, "items must not be None"
    assert context.total_count is not None, "total_count must not be None"

def test_search_products_returns_valid_search_context_contract(monkeypatch):
    products = [
        make_product(
            1,
            "Nike Air Max",
            brand="nike",
            sku="NK-1",
            size="44",
        ),
    ]

    def fake_get_products_by_query(
        db,
        q,
        size=None,
        category=None,
        style_group=None,
        brand=None,
        limit=200,
        offset=0,
    ):
        return products, len(products)

    monkeypatch.setattr(
        product_service,
        "get_products_by_query",
        fake_get_products_by_query,
    )

    monkeypatch.setattr(product_service.cache_service, "get", lambda key: None)
    monkeypatch.setattr(product_service.cache_service, "set", lambda *args, **kwargs: None)

    request = SearchRequest(
        raw_query="nike air max 44",
        brand="nike",
        size="44",
        limit=5,
        offset=0,
    )

    result = product_service.search_products(
        db=None,
        request=request,
    )

    assert_search_context_contract(result)

def test_create_new_product_clears_cache(monkeypatch):
    product_service.cache_service._cache_store["some_search_key"] = {
        "value": "stale result",
        "expires_at": None,
    }

    fake_product = make_product(1, "Nike Air Max", brand="nike", sku="NK-1")

    monkeypatch.setattr(
        product_service,
        "create_product",
        lambda db, product_data: fake_product,
    )

    product_service.create_new_product(db=None, product_data=None)

    assert product_service.cache_service._cache_store == {}