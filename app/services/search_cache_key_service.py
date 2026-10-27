def build_search_cache_key(
    normalized_query: str,
    detected_brand: str | None,
    size: str | None,
    category: str | None,
    style_group: str | None,
    strategy_name: str,
    limit: int,
    offset: int,
) -> str:
    return (
        f"search:products:{normalized_query}"
        f":brand={detected_brand}"
        f":size={size}"
        f":category={category}"
        f":style_group={style_group}"
        f":strategy={strategy_name}"
        f":limit={limit}"
        f":offset={offset}"
    )