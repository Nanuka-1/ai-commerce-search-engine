from app.schemas.search_context import SearchContext


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
    assert context.limit is not None, "limit must not be None"
    assert context.offset is not None, "offset must not be None"

from types import SimpleNamespace

from app.schemas.search_request import SearchRequest
from app.services import product_service


def make_product(
    product_id,
    name,
    brand="nike",
    sku="SKU-1",
    price=100.0,
    size=None,
):
    return SimpleNamespace(
        id=product_id,
        name=name,
        brand=brand,
        sku=sku,
        price=price,
        size=size,
    )


def test_model_search_returns_valid_search_context_contract(monkeypatch):
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



def test_brand_size_search_returns_valid_search_context_contract(monkeypatch):
    products = [
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
        return products, len(products)

    monkeypatch.setattr(
        product_service,
        "get_products_by_query",
        fake_get_products_by_query,
    )

    monkeypatch.setattr(product_service.cache_service, "get", lambda key: None)
    monkeypatch.setattr(product_service.cache_service, "set", lambda *args, **kwargs: None)

    request = SearchRequest(
        raw_query="nike 44",
        brand="nike",
        size="44",
        limit=5,
        offset=0,
    )

    result = product_service.search_products(
        db=None,
        request=request,
    )

    assert result.search_strategy == "brand_size"
    assert_search_context_contract(result)


def test_broad_search_returns_valid_search_context_contract(monkeypatch):
    products = [
        make_product(
            1,
            "Nike Runner",
            brand="nike",
            sku="NK-RUN-1",
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
        raw_query="nike",
        limit=5,
        offset=0,
    )

    result = product_service.search_products(
        db=None,
        request=request,
    )

    assert result.search_strategy == "broad_search"
    assert_search_context_contract(result)


def test_sku_search_returns_valid_search_context_contract(monkeypatch):
    product = make_product(
        1,
        "Nike Air Max",
        brand="nike",
        sku="NK-123",
        size="44",
    )

    def fake_get_product_by_sku(db, sku):
        if sku == "NK-123":
            return product

        return None

    monkeypatch.setattr(
        product_service,
        "get_product_by_sku",
        fake_get_product_by_sku,
    )

    monkeypatch.setattr(product_service.cache_service, "get", lambda key: None)
    monkeypatch.setattr(product_service.cache_service, "set", lambda *args, **kwargs: None)

    result = product_service.get_product_by_sku_service(
        db=None,
        sku="NK-123",
    )

    assert result.search_strategy == "exact_sku"
    assert result.matched_by == "exact_sku"
    assert_search_context_contract(result)

def test_sku_fallback_returns_valid_search_context_contract(monkeypatch):
    product = make_product(
        1,
        "Nike Air Max",
        brand="nike",
        sku="NK-123",
        size="42",
    )

    def fake_get_product_by_sku(db, sku):
        if sku == "NK-123-42":
            return None

        if sku == "NK-123":
            return product

        return None

    monkeypatch.setattr(
        product_service,
        "get_product_by_sku",
        fake_get_product_by_sku,
    )

    monkeypatch.setattr(product_service.cache_service, "get", lambda key: None)
    monkeypatch.setattr(product_service.cache_service, "set", lambda *args, **kwargs: None)

    result = product_service.get_product_by_sku_service(
        db=None,
        sku="NK-123-42",
    )

    assert result.search_strategy == "sku_fallback"
    assert result.matched_by == "sku"

    assert_search_context_contract(result)


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
    assert context.limit is not None, "limit must not be None"
    assert context.offset is not None, "offset must not be None"

    for item in context.items:
        assert isinstance(item, dict), "SearchContext.items must contain dict items"