
from sqlalchemy.orm import Session
from app.repositories.product_repository import (
    get_products_by_query,
    get_products_by_size,
    get_product_by_sku,
    create_product,
    search_same_brand_size_products,
)
from app.schemas.product import ProductCreate
from app.services import cache_service
from app.schemas.search_context import SearchContext
from app.schemas.search_request import SearchRequest
from app.services.product_ranking_service import (
    rank_products,
    parse_sku_parts,
)
from app.services.query_parser_service import (
    extract_brand_from_query,
)
from app.services.search_preparation_service import prepare_search

CANDIDATE_LIMIT = 50



BRAND_ALIASES = {
    "ნაიკი": "nike",
    "ადიდასი": "adidas",
    "პუმა": "puma",
    "რიბოკი": "reebok",
    "ნიუ ბალანსი": "new balance",
}

def serialize_product(product) -> dict:
    return {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "brand": product.brand,
        "price": product.price,
        "size": product.size,
    }



def tokenize_query(query: str) -> list[str]:
    return query.split()



def extract_category_from_query(query: str) -> str | None:
    query = query.lower()

    if any(word in query for word in ["women", "woman", "female", "ქალის", "qali"]):
        return "qalis"

    if any(word in query for word in ["men", "man", "male", "მამაკაცის", "mamakatsis"]):
        return "mamakatsis"

    if any(word in query for word in ["kids", "kid", "children", "child", "ბავშვის", "bavshvis"]):
        return "bavshvis"

    return None


def build_matched_by(
    strategy_name: str,
    fallback_used: bool = False,
) -> str:
    if fallback_used:
        return f"{strategy_name}_fallback"

    return strategy_name


def execute_model_search(
    db: Session,
    request: SearchRequest,
    normalized_query: str,
    model_hint: str | None,
    product_intent,
    effective_category: str | None,
    strategy_name: str,
    cache_key: str,
):
    print("EXECUTE STRATEGY: model_search")

    primary_query = model_hint or normalized_query
    detected_brand = request.brand or extract_brand_from_query(normalized_query)

    items, total_count = get_products_by_query(
        db,
        primary_query,
        size=request.size,
        category=effective_category,
        style_group=product_intent.style_group.value if product_intent else None,
        brand=detected_brand,
        limit=200,
        offset=0,
    )

    if total_count == 0:
        if detected_brand:
            items, total_count = search_same_brand_size_products(
                db=db,
                brand=detected_brand,
                size=request.size,
                category=effective_category,
                style_group=product_intent.style_group.value if product_intent else None,
                limit=200,
            )

        matched_by = "similar_model_same_brand_size"
    else:
        matched_by = "exact_model_same_brand_size"

    paginated_items = items[request.offset: request.offset + request.limit]
    serialized_items = [serialize_product(item) for item in paginated_items]

    context = SearchContext(
        query=request.raw_query,
        normalized_query=normalized_query,
        matched_by=matched_by,
        search_strategy=strategy_name,
        model_hint=model_hint,
        detected_size=request.size,
        detected_category=effective_category,
        product_intent=product_intent,
        items=serialized_items,
        total_count=total_count,
        limit=request.limit,
        offset=request.offset,
    )

    cache_service.set(cache_key, context, ttl=60)

    return context


def execute_brand_size_search(
    db: Session,
    request: SearchRequest,
    normalized_query: str,
    product_intent,
    effective_category: str | None,
    strategy_name: str,
    cache_key: str,
):
    print("EXECUTE STRATEGY: brand_size")

    primary_query = request.brand or extract_brand_from_query(normalized_query)

    items, total_count = get_products_by_query(
        db,
        primary_query,
        size=request.size,
        category=effective_category,
        style_group=product_intent.style_group.value if product_intent else None,
        brand=primary_query,
        limit=200,
        offset=0,
    )

    paginated_items = items[request.offset: request.offset + request.limit]
    serialized_items = [serialize_product(item) for item in paginated_items]

    context = SearchContext(
        query=request.raw_query,
        normalized_query=normalized_query,
        matched_by=build_matched_by(strategy_name),
        search_strategy=strategy_name,
        model_hint=None,
        detected_color=request.color,
        detected_size=request.size,
        detected_category=effective_category,
        product_intent=product_intent,
        items=serialized_items,
        total_count=total_count,
        limit=request.limit,
        offset=request.offset,
    )

    cache_service.set(cache_key, context, ttl=60)

    return context

def execute_broad_search(
    db: Session,
    request: SearchRequest,
    normalized_query: str,
    model_hint: str | None,
    product_intent,
    usage_type: str | None,
    effective_category: str | None,
    strategy_name: str,
    cache_key: str,
):
    print("EXECUTE STRATEGY: broad_search")

    detected_brand = request.brand or extract_brand_from_query(normalized_query)

    primary_query = model_hint or normalized_query
    matched_by = "query"

    items, total_count = get_products_by_query(
        db,
        primary_query,
        size=request.size,
        category=effective_category,
        style_group=product_intent.style_group.value if product_intent else None,
        brand=detected_brand,
        limit=CANDIDATE_LIMIT,
        offset=0,
    )

    if total_count == 0 and detected_brand:
        items, total_count = get_products_by_query(
            db,
            detected_brand,
            size=request.size,
            category=effective_category,
            style_group=product_intent.style_group.value if product_intent else None,
            brand=detected_brand,
            limit=200,
            offset=0,
        )
        normalized_query = detected_brand
        matched_by = "brand_fallback"

    if total_count == 0 and request.size:
        items, total_count = get_products_by_size(
            db=db,
            size=request.size,
            category=effective_category,
            limit=200,
        )
        normalized_query = f"size:{request.size}"
        matched_by = "size_alternatives"

    tokens = tokenize_query(normalized_query)

    items = rank_products(
        products=items,
        tokens=tokens,
        normalized_query=normalized_query,
        usage_type=usage_type,
        model_hint=model_hint,
        requested_size=request.size,
        requested_category=effective_category,
        requested_style_group=product_intent.style_group.value if product_intent else None,
    )

    paginated_items = items[request.offset: request.offset + request.limit]
    serialized_items = [serialize_product(item) for item in paginated_items]

    context = SearchContext(
        query=request.raw_query,
        normalized_query=normalized_query,
        matched_by=matched_by,
        search_strategy=strategy_name,
        model_hint=model_hint,
        detected_color=request.color,
        detected_size=request.size,
        detected_category=effective_category,
        product_intent=product_intent,
        items=serialized_items,
        total_count=total_count,
        limit=request.limit,
        offset=request.offset,
    )

    cache_service.set(cache_key, context, ttl=60)

    return context

def search_products(db: Session, request: SearchRequest):
    preparation = prepare_search(request)

    normalized_query = preparation.normalized_query
    product_intent = preparation.product_intent
    usage_type = preparation.usage_type
    model_hint = preparation.model_hint
    effective_category = preparation.category
    strategy_name = preparation.strategy_name

    print("SEARCH STRATEGY:", strategy_name)

    cache_key = (
        f"search:products:{normalized_query}"
        f":size={request.size}"
        f":category={request.category}"
        f":limit={request.limit}"
        f":offset={request.offset}"
    )

    cached = cache_service.get(cache_key)
    if cached is not None:
        print("CACHE HIT:", cache_key)
        return cached

    print("CACHE MISS:", cache_key)

    if strategy_name == "model_search":
        return execute_model_search(
            db=db,
            request=request,
            normalized_query=normalized_query,
            model_hint=model_hint,
            product_intent=product_intent,
            effective_category=effective_category,
            strategy_name=strategy_name,
            cache_key=cache_key,
        )

    if strategy_name == "brand_size":
        return execute_brand_size_search(
            db=db,
            request=request,
            normalized_query=normalized_query,
            product_intent=product_intent,
            effective_category=effective_category,
            strategy_name=strategy_name,
            cache_key=cache_key,
        )

    return execute_broad_search(
        db=db,
        request=request,
        normalized_query=normalized_query,
        model_hint=model_hint,
        product_intent=product_intent,
        usage_type=usage_type,
        effective_category=effective_category,
        strategy_name=strategy_name,
        cache_key=cache_key,
    )




def get_product_by_sku_service(db: Session, sku: str):
    requested_sku = sku.strip().upper()

    # 1. exact sku search
    exact_cache_key = f"product:sku:exact:{requested_sku}"

    cached = cache_service.get(exact_cache_key)
    if cached is not None:
        print("CACHE HIT:", exact_cache_key)
        return cached

    print("CACHE MISS:", exact_cache_key)

    exact_product = get_product_by_sku(db, requested_sku)

    if exact_product:
        context = SearchContext(
            query=sku,
            normalized_query=requested_sku.lower(),
            requested_sku=requested_sku,
            base_sku=requested_sku,
            detected_size=exact_product.size,
            matched_by="exact_sku",
            items=[exact_product],
            total_count=1,
        )

        cache_service.set(exact_cache_key, context, ttl=60)

        return context

    # 2. fallback parsing
    base_sku, size = parse_sku_parts(requested_sku)

    fallback_cache_key = f"product:sku:fallback:{base_sku}"

    cached = cache_service.get(fallback_cache_key)
    if cached is not None:
        print("CACHE HIT:", fallback_cache_key)
        return cached

    print("CACHE MISS:", fallback_cache_key)

    product = get_product_by_sku(db, base_sku)

    context = SearchContext(
        query=sku,
        normalized_query=base_sku.lower(),
        requested_sku=requested_sku,
        base_sku=base_sku,
        detected_size=size,
        matched_by="sku",
        items=[product] if product else [],
        total_count=1 if product else 0,
    )

    cache_service.set(fallback_cache_key, context, ttl=60)

    return context

def create_new_product(db: Session, product_data: ProductCreate):
    return create_product(db, product_data)

