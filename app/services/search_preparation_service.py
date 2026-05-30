from app.schemas.search_preparation import SearchPreparation
from app.schemas.search_request import SearchRequest

from app.services.product_intent_service import extract_product_intent

from app.services.search_strategy_service import (
    choose_search_strategy,
    get_strategy_name,
)

from app.services.query_parser_service import (
    extract_brand_from_query,
    extract_model_hint_from_query,
    extract_usage_type_from_query,
    normalize_search_query,
)


def prepare_search(request: SearchRequest) -> SearchPreparation:
    normalized_query = normalize_search_query(request.raw_query)

    product_intent = extract_product_intent(normalized_query)
    usage_type = extract_usage_type_from_query(normalized_query)
    model_hint = extract_model_hint_from_query(normalized_query)

    detected_brand = request.brand or extract_brand_from_query(normalized_query)

    search_strategy = choose_search_strategy(
        raw_query=request.raw_query,
        brand=detected_brand,
        size=request.size,
        model_hint=model_hint,
        is_sku=False,
    )

    strategy_name = get_strategy_name(search_strategy)

    return SearchPreparation(
        normalized_query=normalized_query,
        product_intent=product_intent,
        usage_type=usage_type,
        model_hint=model_hint,
        brand=detected_brand,
        category=request.category,
        size=request.size,
        color=request.color,
        strategy_name=strategy_name,
    )