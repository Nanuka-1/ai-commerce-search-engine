from enum import Enum


class SearchStrategy(str, Enum):
    EXACT_SKU = "exact_sku"
    BRAND_SIZE = "brand_size"
    MODEL_SEARCH = "model_search"
    BROAD_SEARCH = "broad_search"
    FALLBACK_ALTERNATIVES = "fallback_alternatives"


def choose_search_strategy(
    raw_query: str,
    brand: str | None = None,
    size: str | None = None,
    model_hint: str | None = None,
    is_sku: bool = False,
) -> SearchStrategy:
    if is_sku:
        return SearchStrategy.EXACT_SKU

    if model_hint:
        return SearchStrategy.MODEL_SEARCH

    if brand and size:
        return SearchStrategy.BRAND_SIZE

    if brand:
        return SearchStrategy.BROAD_SEARCH

    return SearchStrategy.BROAD_SEARCH


def get_strategy_name(strategy: SearchStrategy) -> str:
    return strategy.value