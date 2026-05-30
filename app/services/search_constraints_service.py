from app.schemas.search_constraints import SearchConstraints

from app.services.intent_router import (
    extract_category_from_query,
    extract_color_from_query,
    extract_size_from_query,
)

from app.services.query_parser_service import (
    extract_brand_from_query,
    extract_model_hint_from_query,
)


def extract_constraints_from_message(message: str) -> SearchConstraints:
    return SearchConstraints(
        brand=extract_brand_from_query(message),
        category=extract_category_from_query(message),
        size=extract_size_from_query(message),
        color=extract_color_from_query(message),
        model_hint=extract_model_hint_from_query(message),
    )