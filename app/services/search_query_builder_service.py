from app.schemas.search_constraints import SearchConstraints


def merge_constraints(
    current: SearchConstraints,
    incoming: SearchConstraints,
) -> SearchConstraints:

    return SearchConstraints(
        brand=incoming.brand or current.brand,
        category=incoming.category or current.category,
        size=incoming.size or current.size,
        color=incoming.color or current.color,
        model_hint=incoming.model_hint or current.model_hint,
        usage_type=incoming.usage_type or current.usage_type,
        sport_type=incoming.sport_type or current.sport_type,
    )


def build_query_from_constraints(constraints: SearchConstraints) -> str:
    parts = []

    if constraints.brand:
        parts.append(constraints.brand)

    if constraints.category:
        parts.append(constraints.category)

    if constraints.model_hint:
        parts.append(constraints.model_hint)

    if constraints.usage_type:
        parts.append(constraints.usage_type)

    if constraints.sport_type:
        parts.append(constraints.sport_type)

    if constraints.color:
        parts.append(constraints.color)

    if constraints.size:
        parts.append(constraints.size)

    return " ".join(parts)
