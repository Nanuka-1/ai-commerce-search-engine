from types import SimpleNamespace

from app.schemas.search_context import SearchContext
from app.schemas.search_request import SearchRequest
from app.services.search_decision_service import apply_search_decision


def make_product(name="Nike Air Max", sku="ABC123"):
    return SimpleNamespace(
        id=1,
        sku=sku,
        name=name,
        price=100,
    )


def test_decision_need_model_when_size_exists_but_model_missing():
    context = SearchContext(
        query="nike 44",
        normalized_query="nike 44",
        items=[make_product(name="Nike Shoes")],
        total_count=14,
        limit=5,
        offset=0,
    )

    request = SearchRequest(
        raw_query="nike 44",
        size="44",
        limit=5,
        offset=0,
    )

    result = apply_search_decision(context, request)

    assert result.result_mode == "need_model"
    assert result.needs_clarification is True
    assert result.clarification_reason == "missing_model"


def test_decision_need_size_when_model_exists_but_size_missing():
    context = SearchContext(
        query="nike air max",
        normalized_query="air max",
        model_hint="air max",
        items=[make_product(name="Nike Air Max")],
        total_count=1,
        limit=5,
        offset=0,
    )

    request = SearchRequest(
        raw_query="nike air max",
        size=None,
        limit=5,
        offset=0,
    )

    result = apply_search_decision(context, request)

    assert result.result_mode == "need_size"
    assert result.needs_clarification is True
    assert result.clarification_reason == "missing_size"


def test_decision_fallback_similar_when_model_not_found_but_similar_items_exist():
    context = SearchContext(
        query="nike air max 44",
        normalized_query="nike",
        model_hint="air max",
        items=[make_product(name="Nike Shoes")],
        total_count=10,
        limit=5,
        offset=0,
    )

    request = SearchRequest(
        raw_query="nike air max 44",
        size="44",
        limit=5,
        offset=0,
    )

    result = apply_search_decision(context, request)

    assert result.result_mode == "fallback_similar"
    assert result.needs_clarification is True
    assert result.clarification_reason == "exact_model_not_found"


def test_decision_exact_model_match():
    context = SearchContext(
        query="nike air max 44",
        normalized_query="air max",
        model_hint="air max",
        items=[make_product(name="Nike Air Max")],
        total_count=1,
        limit=5,
        offset=0,
    )

    request = SearchRequest(
        raw_query="nike air max 44",
        size="44",
        limit=5,
        offset=0,
    )

    result = apply_search_decision(context, request)

    assert result.result_mode == "exact_model_match"
    assert result.needs_clarification is False
    assert result.clarification_reason is None


def test_exact_model_not_found_sets_fallback_similar_mode():
    context = SearchContext(
        query="nike air unknown",
        normalized_query="nike air unknown",
        model_hint="air unknown",
        items=[
            make_product(name="Nike Air Max", sku="ABC123"),
            make_product(name="Nike Runner", sku="XYZ456"),
        ],
        total_count=2,
        limit=5,
        offset=0,
    )

    request = SearchRequest(
        raw_query="nike air unknown 44",
        size="44",
        limit=5,
        offset=0,
    )

    result = apply_search_decision(context, request)

    assert result.needs_clarification is True
    assert result.clarification_reason == "exact_model_not_found"
    assert result.result_mode == "fallback_similar"