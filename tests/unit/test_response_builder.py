from types import SimpleNamespace

from app.services.response_builder import build_response
from app.schemas.search_context import SearchContext


def make_product(product_id: int):
    return SimpleNamespace(
        id=product_id,
        sku=f"SKU-{product_id}",
        name=f"Product {product_id}",
        price=100.0,
    )


from types import SimpleNamespace

from app.services.response_builder import build_response
from app.schemas.search_context import SearchContext


def make_product(product_id: int):
    return SimpleNamespace(
        id=product_id,
        sku=f"SKU-{product_id}",
        name=f"Product {product_id}",
        price=100.0,
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