def normalize_search_query(query: str) -> str:
    return query.strip().lower()


KNOWN_BRANDS = [
    "nike",
    "adidas",
    "puma",
    "reebok",
    "new balance",
    "under armour",
]


MODEL_KEYWORDS = [
    "air max",
    "jordan",
    "ultraboost",
    "superstar",
    "pegasus",
    "zoom",
    "react",
]


def extract_brand_from_query(query: str) -> str | None:
    normalized_query = normalize_search_query(query)

    for brand in KNOWN_BRANDS:
        if brand in normalized_query:
            return brand

    return None


def extract_model_hint_from_query(query: str) -> str | None:
    normalized_query = normalize_search_query(query)

    for model in MODEL_KEYWORDS:
        if model in normalized_query:
            return model

    return None


def extract_usage_type_from_query(query: str) -> str | None:
    normalized_query = normalize_search_query(query)

    if "running" in normalized_query:
        return "running"

    if "football" in normalized_query:
        return "football"

    if "basketball" in normalized_query:
        return "basketball"

    if "casual" in normalized_query:
        return "casual"

    return None