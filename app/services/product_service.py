import logging
import time
from sqlalchemy.orm import Session
from app.repositories.product_repository import (
    get_products_by_query,
    get_products_by_size,
    get_product_by_sku,
    get_products_by_page,
    create_product,
)
from app.schemas.product import ProductCreate
from app.services import cache_service
from app.schemas.search_context import SearchContext
from app.schemas.search_request import SearchRequest
from app.services.product_ranking_service import (
    rank_products,
    parse_sku_parts,
    tokenize_query,
)
from app.services.query_parser_service import (
    extract_brand_from_query,
)
from app.services.search_preparation_service import prepare_search
from app.schemas.fallback_level import FallbackLevel
from app.services.product_fallback_service import (
    execute_model_fallback_search,
    execute_fallback_chain,
    FallbackStep,
)
from app.services.product_serializer import (
    serialize_product,
    serialize_products,
    serialize_model_cards,
)
from app.services.product_grouping_service import group_variants_by_model
from app.services.hybrid_search_service import apply_hybrid, prefetch_query_vector
from app.services.search_cache_key_service import build_search_cache_key
from app.services import request_timings

logger = logging.getLogger(__name__)

CANDIDATE_LIMIT = 50

def build_matched_by(
    strategy_name: str,
    fallback_used: bool = False,
) -> str:
    if fallback_used:
        return f"{strategy_name}_fallback"

    return strategy_name


def resolve_style_group(product_intent) -> str | None:
    if product_intent is None:
        return None

    if product_intent.style_group is None:
        return None

    return product_intent.style_group.value


def paginate_items(
    items: list,
    offset: int,
    limit: int,
) -> list:
    return items[offset: offset + limit]


# --- U2.3 (12.10): «до N лари» / «только со скидкой» ---

def deal_filters(request: SearchRequest) -> dict:
    """Аргументы фильтров для репозитория (база отбирает, а не мы после).
    Без фильтров — пустой словарь: вызовы репозитория остаются ровно такими, как раньше."""
    if not has_deal_filters(request):
        return {}
    filters = {"max_price": getattr(request, "max_price", None),
               "discount_only": getattr(request, "discount_only", False)}
    if getattr(request, "new_only", False):
        filters["new_only"] = True          # 21.10: только когда включено — старые вызовы не меняются
    # 26.10: «другой бренд» — сам по себе, а не только вместе с новинками
    # (раньше этот if стоял ВНУТРИ if new_only → без новинок бренды не исключались)
    if getattr(request, "exclude_brands", None):
        filters["exclude_brands"] = list(request.exclude_brands)
    return filters


def has_deal_filters(request) -> bool:
    # getattr: в тестах и старом коде запрос бывает «упрощённым» объектом без этих полей
    return bool(getattr(request, "max_price", None) or getattr(request, "discount_only", False)
                or getattr(request, "new_only", False) or getattr(request, "exclude_brands", None))


def discount_share(item) -> float:
    price = getattr(item, "price", None)
    regular = getattr(item, "regular_price", None)
    if not price or not regular or regular <= price:
        return 0.0
    return (regular - price) / regular


def order_by_discount(items: list, request: SearchRequest) -> list:
    """«Со скидкой» / «сначала со скидкой» → самые большие скидки первыми (−70% раньше −20%),
    без скидки — после, в прежнем порядке. Иначе порядок ранжирования."""
    if not (getattr(request, "discount_only", False) or getattr(request, "prefer_discount", False)):
        return items
    return sorted(items, key=discount_share, reverse=True)   # sorted устойчив: при равной скидке — порядок ранжирования


def card_discount_share(card) -> float:
    price = card.get("price_from") or card.get("price")
    regular = card.get("regular_price")
    if not price or not regular or regular <= price:
        return 0.0
    return (regular - price) / regular


def prefer_discounted_cards(context, request: SearchRequest):
    """13.10: после слияния со смысловым поиском снова ставим карточки со скидкой первыми (только для prefer_discount)."""
    if not getattr(request, "prefer_discount", False) or not getattr(context, "items", None):
        return context
    items = sorted(context.items, key=lambda card: card_discount_share(card) if isinstance(card, dict) else 0.0,
                   reverse=True)
    if hasattr(context, "model_copy"):
        return context.model_copy(update={"items": items})
    context.items = items
    return context


def group_into_model_cards(items: list, total_count: int):
    """Варианты одной модели (страницы) -> одна карточка с размерами и ценой "от".
    total_count пересчитываем в модели, только если загружены все найденные варианты;
    иначе (кандидатов больше лимита) оставляем число из БД."""
    cards = group_variants_by_model(items)
    if len(items) >= total_count:
        total_count = len(cards)
    return cards, total_count


def execute_model_search(
    db: Session,
    request: SearchRequest,
    normalized_query: str,
    model_hint: str | None,
    detected_brand: str | None,
    product_intent,
    effective_category: str | None,
    strategy_name: str,
    cache_key: str,
    usage_type: str | None = None,   # <-- new
):

    primary_query = model_hint or normalized_query


    fallback_level = FallbackLevel.EXACT_MODEL.value
    alternative_reason = None

    items, total_count = get_products_by_query(
        db,
        primary_query,
        size=request.size,
        category=effective_category,
        style_group=resolve_style_group(product_intent),
        brand=detected_brand,
        limit=200,
        offset=0,
        **deal_filters(request),
    )

    # Запасной поиск модели (тот же бренд/размер) не знает фильтров цены → при фильтрах не используем:
    # лучше честное «не нашли», чем товары дороже бюджета / без скидки.
    if total_count == 0 and not has_deal_filters(request):
        fallback_result = execute_model_fallback_search(
            db=db,
            detected_brand=detected_brand,
            size=request.size,
            effective_category=effective_category,
            style_group=resolve_style_group(product_intent),
            limit=200,
        )

        items = fallback_result.items
        total_count = fallback_result.total_count
        fallback_level = fallback_result.fallback_level
        alternative_reason = fallback_result.alternative_reason
        matched_by = fallback_result.matched_by
    else:
        matched_by = "exact_model_same_brand_size"


    tokens = tokenize_query(normalized_query)

    items = rank_products(
        products=items,
        tokens=tokens,
        normalized_query=normalized_query,
        usage_type=usage_type,
        model_hint=model_hint,
        requested_size=request.size,
        requested_category=effective_category,
        requested_style_group=resolve_style_group(product_intent),
        requested_color=request.color,
    )
    items = order_by_discount(items, request)

    cards, total_count = group_into_model_cards(items, total_count)

    paginated_cards = paginate_items(
        cards,
        request.offset,
        request.limit,
    )

    serialized_items = serialize_model_cards(
        paginated_cards
    )

    context = SearchContext(
        query=request.raw_query,
        normalized_query=normalized_query,
        matched_by=matched_by,
        search_strategy=strategy_name,
        retrieval_mode="keyword",
        fallback_level=fallback_level,
        alternative_reason=alternative_reason,
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


def execute_brand_size_search(
    db: Session,
    request: SearchRequest,
    normalized_query: str,
    detected_brand: str | None,
    product_intent,
    effective_category: str | None,
    strategy_name: str,
    cache_key: str,
    usage_type: str | None = None,
):


    primary_query = detected_brand

    items, total_count = get_products_by_query(
        db,
        primary_query,
        size=request.size,
        category=effective_category,
        style_group=resolve_style_group(product_intent),
        brand=primary_query,
        limit=200,
        offset=0,
        **deal_filters(request),
    )

    tokens = tokenize_query(normalized_query)

    items = rank_products(
        products=items,
        tokens=tokens,
        normalized_query=normalized_query,
        usage_type=usage_type,
        model_hint=None,
        requested_size=request.size,
        requested_category=effective_category,
        requested_style_group=resolve_style_group(product_intent),
        requested_color=request.color,
    )
    items = order_by_discount(items, request)



    cards, total_count = group_into_model_cards(items, total_count)

    paginated_cards = paginate_items(
        cards,
        request.offset,
        request.limit,
    )

    serialized_items = serialize_model_cards(
        paginated_cards
    )

    context = SearchContext(
        query=request.raw_query,
        normalized_query=normalized_query,
        matched_by=build_matched_by(strategy_name),
        search_strategy=strategy_name,
        retrieval_mode="keyword",
        fallback_level=None,
        alternative_reason=None,
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
    detected_brand: str | None,
    product_intent,
    usage_type: str | None,
    effective_category: str | None,
    strategy_name: str,
    cache_key: str,
):

    primary_query = model_hint or normalized_query
    matched_by = "query"
    fallback_level = None
    alternative_reason = None

    items, total_count = get_products_by_query(
        db,
        primary_query,
        size=request.size,
        category=effective_category,
        style_group=resolve_style_group(product_intent),
        brand=detected_brand,
        limit=CANDIDATE_LIMIT,
        offset=0,
        **deal_filters(request),
    )

    if total_count == 0:
        steps: list[FallbackStep] = []

        if detected_brand:
            steps.append(
                FallbackStep(
                    fetch=lambda: get_products_by_query(
                        db,
                        detected_brand,
                        size=request.size,
                        category=effective_category,
                        style_group=resolve_style_group(product_intent),
                        brand=detected_brand,
                        limit=200,
                        offset=0,
                        **deal_filters(request),
                    ),
                    fallback_level=FallbackLevel.BRAND_ONLY.value,
                    alternative_reason="query_not_found",
                    matched_by="brand_fallback",
                )
            )

        if request.size:
            steps.append(
                FallbackStep(
                    fetch=lambda: get_products_by_size(
                        db=db,
                        size=request.size,
                        category=effective_category,
                        limit=200,
                        **deal_filters(request),
                    ),
                    fallback_level=FallbackLevel.SAME_SIZE.value,
                    alternative_reason="brand_not_found",
                    matched_by="size_alternatives",
                )
            )

        fallback_result = execute_fallback_chain(steps)

        if fallback_result.total_count > 0:
            items = fallback_result.items
            total_count = fallback_result.total_count
            fallback_level = fallback_result.fallback_level
            alternative_reason = fallback_result.alternative_reason
            matched_by = fallback_result.matched_by

            if matched_by == "brand_fallback":
                normalized_query = detected_brand
            elif matched_by == "size_alternatives":
                normalized_query = f"size:{request.size}"

    tokens = tokenize_query(normalized_query)

    items = rank_products(
        products=items,
        tokens=tokens,
        normalized_query=normalized_query,
        usage_type=usage_type,
        model_hint=model_hint,
        requested_size=request.size,
        requested_category=effective_category,
        requested_style_group=resolve_style_group(product_intent),
        requested_color=request.color,
    )
    items = order_by_discount(items, request)

    cards, total_count = group_into_model_cards(items, total_count)

    paginated_cards = paginate_items(
        cards,
        request.offset,
        request.limit,
    )

    serialized_items = serialize_model_cards(
        paginated_cards
    )

    context = SearchContext(
        query=request.raw_query,
        normalized_query=normalized_query,
        matched_by=matched_by,
        search_strategy=strategy_name,

        retrieval_mode="keyword",
        fallback_level=fallback_level,
        alternative_reason=alternative_reason,

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
    detected_brand = request.brand or extract_brand_from_query(normalized_query)

    logger.info(
        "Search strategy selected",
        extra={
            "strategy": strategy_name,
        },
    )



    # 16.10: вектор запроса — в фоне, пока идёт точный поиск (не ждём Gemini по очереди)
    prefetch_query_vector(db, request, strategy_name)

    style_group = (
        product_intent.style_group.value
        if product_intent and product_intent.style_group
        else None
    )

    cache_key = build_search_cache_key(
        normalized_query=normalized_query,
        detected_brand=detected_brand,
        size=request.size,
        category=effective_category,
        style_group=style_group,
        strategy_name=strategy_name,
        limit=request.limit,
        offset=request.offset,
    )
    if has_deal_filters(request):
        # тот же запрос с фильтрами и без — разные результаты → разные ключи кэша
        cache_key = (f"{cache_key}:max={request.max_price}:discount={request.discount_only}"
                                          f":new={getattr(request, 'new_only', False)}"
                     f":nobrand={','.join(getattr(request, 'exclude_brands', None) or [])}")
    if getattr(request, "prefer_discount", False):
        cache_key = f"{cache_key}:prefer_discount"          # другой порядок — другой ключ

    cached = cache_service.get(cache_key)

    if cached is not None:
        if has_deal_filters(request):
            return cached
        # В кэше — результат ТОЧНОГО поиска; смысловой добавляется поверх (у него свой кэш).
        return prefer_discounted_cards(
            apply_hybrid(db, request, cached, brand=detected_brand, category=effective_category), request)


    stage_started = time.perf_counter()     # 15.10: замер точного поиска (SQL + ранжирование + карточки)

    if strategy_name == "model_search":
        context = execute_model_search(
            db=db,
            request=request,
            normalized_query=normalized_query,
            model_hint=model_hint,
            detected_brand=detected_brand,
            product_intent=product_intent,
            effective_category=effective_category,
            strategy_name=strategy_name,
            cache_key=cache_key,
            usage_type=usage_type,
        )
    elif strategy_name == "brand_size":
        context = execute_brand_size_search(
            db=db,
            request=request,
            normalized_query=normalized_query,
            detected_brand=detected_brand,
            product_intent=product_intent,
            effective_category=effective_category,
            strategy_name=strategy_name,
            cache_key=cache_key,
            usage_type=usage_type,
        )
    else:
        context = execute_broad_search(
            db=db,
            request=request,
            normalized_query=normalized_query,
            model_hint=model_hint,
            detected_brand=detected_brand,
            product_intent=product_intent,
            usage_type=usage_type,
            effective_category=effective_category,
            strategy_name=strategy_name,
            cache_key=cache_key,
        )

        request_timings.record("search.keyword", stage_started)

    if has_deal_filters(request):
        # Смысловой поиск не знает цен → при «до N лари / со скидкой» показываем только отфильтрованный точный.
        return context

    # Шаг 3.6: слияние с смысловым поиском. Выключено / нет Gemini / не Postgres → точный без изменений.
    return prefer_discounted_cards(
        apply_hybrid(db, request, context, brand=detected_brand, category=effective_category), request)




def get_product_by_sku_service(db: Session, sku: str):
    requested_sku = sku.strip().upper()

    # 1. exact sku search
    exact_cache_key = f"product:sku:exact:{requested_sku}"

    cached = cache_service.get(exact_cache_key)

    if cached is not None:
        return cached


    exact_product = get_product_by_sku(db, requested_sku)

    if exact_product:
        context = SearchContext(
            query=sku,
            normalized_query=requested_sku.lower(),
            requested_sku=requested_sku,
            base_sku=requested_sku,
            detected_size=exact_product.size,
            matched_by="exact_sku",
            search_strategy="exact_sku",
            retrieval_mode="keyword",
            fallback_level=None,
            alternative_reason=None,
            items=[serialize_product(exact_product)],
            total_count=1,
        )

        cache_service.set(exact_cache_key, context, ttl=60)

        return context

    # 2. fallback parsing
    base_sku, size = parse_sku_parts(requested_sku)

    fallback_cache_key = f"product:sku:fallback:{base_sku}"

    cached = cache_service.get(fallback_cache_key)

    if cached is not None:
        return cached

    product = get_product_by_sku(db, base_sku)

    context = SearchContext(
        query=sku,
        normalized_query=base_sku.lower(),
        requested_sku=requested_sku,
        base_sku=base_sku,
        detected_size=size,
        matched_by="sku",
        search_strategy="sku_fallback",
        retrieval_mode="keyword",
        fallback_level=None,
        alternative_reason=None,
        items=serialize_products([product]) if product else [],
        total_count=1 if product else 0,
    )

    cache_service.set(fallback_cache_key, context, ttl=60)

    return context


def get_model_cards_by_page(db: Session, page: str) -> list[dict]:
    """26.10 (этап 3, п.2): ссылка на товар → карточка этой модели (все размеры, цена «от»)
    — те же группировка и карточки, что у обычного поиска."""
    return serialize_model_cards(group_variants_by_model(get_products_by_page(db, page)))


def create_new_product(db: Session, product_data: ProductCreate):
    product = create_product(db, product_data)
    cache_service.clear()
    return product