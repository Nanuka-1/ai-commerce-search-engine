import re


USAGE_SYNONYMS = {
    "running": ["running", "sport", "training", "სპორტული"],
    "casual": ["casual", "lifestyle", "daily", "ყოველდღიური"],
}


def parse_sku_parts(sku: str | None) -> tuple[str, str | None]:
    if not sku:
        return "", None

    cleaned = sku.strip().upper()

    match = re.match(r"^(.+?-\d+)-(\d+(?:\.\d+)?)$", cleaned)
    if match:
        base_sku = match.group(1)
        size = match.group(2)
        return base_sku, size

    return cleaned, None


def normalize_sku(sku: str | None) -> str:
    base_sku, _ = parse_sku_parts(sku)
    return base_sku.lower()


def build_search_text(product) -> str:
    parts = []

    if product.name:
        parts.append(product.name)

    if getattr(product, "brand", None):
        parts.append(product.brand)

    if product.sku:
        parts.append(normalize_sku(product.sku))

    return " ".join(parts).strip().lower()


def score_product(
    product,
    tokens: list[str],
    normalized_query: str,
    usage_type: str | None,
    model_hint: str | None,
    requested_size: str | None = None,
    requested_category: str | None = None,
    requested_style_group: str | None = None,
) -> int:
    name_text = (product.name or "").lower()
    brand_text = (getattr(product, "brand", "") or "").lower()
    sku_text = normalize_sku(product.sku or "").lower()
    search_text = build_search_text(product)

    score = 0
    matched_tokens = 0

    if requested_size and str(product.size) == str(requested_size):
        score += 50

    if requested_category and product.category_slug and requested_category in product.category_slug:
        score += 35

    if requested_style_group and product.style_group == requested_style_group:
        score += 30

    for token in tokens:
        token_matched = False

        if token and token in sku_text:
            score += 25
            token_matched = True

        if token and token in brand_text:
            score += 20
            token_matched = True

        if token and token in name_text:
            score += 10
            token_matched = True

            if name_text.startswith(token):
                score += 5

        if token_matched:
            matched_tokens += 1

    if tokens and matched_tokens == len(tokens):
        score += 20

    if normalized_query and normalized_query in name_text:
        score += 30

    if normalized_query and normalized_query in brand_text:
        score += 20

    if normalized_query and normalized_query in sku_text:
        score += 40

    if usage_type:
        synonyms = USAGE_SYNONYMS.get(usage_type, [])
        if any(word in search_text for word in synonyms):
            score += 15

    if model_hint and model_hint in search_text:
        score += 40

    score += max(0, 20 - len(search_text) // 5)

    return score


def rank_products(
    products,
    tokens: list[str],
    normalized_query: str,
    usage_type: str | None,
    model_hint: str | None,
    requested_size: str | None = None,
    requested_category: str | None = None,
    requested_style_group: str | None = None,
):
    return sorted(
        products,
        key=lambda product: score_product(
            product=product,
            tokens=tokens,
            normalized_query=normalized_query,
            usage_type=usage_type,
            model_hint=model_hint,
            requested_size=requested_size,
            requested_category=requested_category,
            requested_style_group=requested_style_group,
        ),
        reverse=True,
    )