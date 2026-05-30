from types import SimpleNamespace

from app.schemas.search_request import SearchRequest
from app.schemas.search_context import SearchContext
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