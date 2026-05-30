from app.schemas.search_request import SearchRequest

from app.services.intent_router import (
    extract_category_from_query,
    extract_color_from_query,
    extract_size_from_query,
    map_category_to_db_slug,
)

from app.services.query_parser_service import extract_brand_from_query


def build_search_request(
    message: str,
    limit: int,
    offset: int,
) -> SearchRequest:
    size = extract_size_from_query(message)
    brand = extract_brand_from_query(message)
    semantic_category = extract_category_from_query(message)
    category = map_category_to_db_slug(semantic_category)
    color = extract_color_from_query(message)

    return SearchRequest(
        raw_query=message,
        intent="product_search",
        size=size,
        brand=brand,
        category=category,
        color=color,
        limit=limit,
        offset=offset,
    )