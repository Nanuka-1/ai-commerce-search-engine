"""
Гибридный поиск (шаг 3.6): слияние ТОЧНОГО (keyword) и СМЫСЛОВОГО (vector) поиска.

  точный поиск (как раньше)  ─┐
                              ├─ слияние RRF по местам в списках ─→ карточки + пометка источника
  смысловой поиск (Gemini)   ─┘

Принципы:
  - Фильтры общие: смысловой ищет только среди разрешённых правилами (размер, бренд, пол, активные).
  - RRF (Reciprocal Rank Fusion): очки = 1/(60 + место в точном) + 1/(60 + место в смысловом).
    Сравниваются МЕСТА, не баллы — у двух поисков несравнимые шкалы.
  - Смысловые совпадения сильно хуже лучшего (> SEMANTIC_MARGIN) отбрасываются — относительный порог
    (замер 06.10: хорошие 0.63–0.73, мусор ~0.58).
  - Если Gemini недоступен / лимит / не Postgres / выключено — возвращается точный результат БЕЗ изменений.
  - У каждой карточки: source = keyword | semantic | both, similarity (если нашёл смысловой). Для нас, не для клиента.
  - Смысловой НЕ нужен (шаг 3.6b), когда клиент уже назвал точно, что ищет:
      модель из MODEL_FAMILIES (стратегия model_search: pegasus, air max 90 42, pegasos) и артикул.
    Там только точный поиск + бизнес-правила (need_size, альтернативы) — без Gemini.

Включение: в .env SEMANTIC_SEARCH_ENABLED=true (по умолчанию выключено — тесты на SQLite не трогает).
"""
import logging
import os

from app.services import cache_service
from app.services import request_timings

logger = logging.getLogger(__name__)

RRF_K = 60
SEMANTIC_LIMIT = 20          # сколько ближайших берём из смыслового поиска
SEMANTIC_MARGIN = 0.08       # смысловое совпадение не хуже лучшего более чем на 0.08
SEMANTIC_FLOOR = 0.62        # абсолютная планка (замер 12.10): мусор 0.55–0.61, худший осмысленный 0.641
SEMANTIC_CACHE_TTL = 600     # повтор того же запроса — без нового обращения к Gemini


def is_enabled() -> bool:
    return os.getenv("SEMANTIC_SEARCH_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


PRECISE_STRATEGIES = {"model_search"}   # клиент назвал известную модель — смысл не нужен


def needs_semantic(query: str | None, strategy: str | None) -> bool:
    """Нужен ли смысловой поиск. Нет — для известной модели и для артикула."""
    from app.services.intent_router import is_sku

    if strategy in PRECISE_STRATEGIES:
        return False
    if is_sku(query or ""):
        return False
    return True


def page_of(product_url: str | None) -> str:
    return (product_url or "").split("?")[0]


def filter_semantic(results: list[tuple[str, float]], margin: float = SEMANTIC_MARGIN,
                    floor: float = SEMANTIC_FLOOR):
    """Оставить совпадения не ниже планки (floor) и близкие к лучшему (относительный порог margin)."""
    results = [(page, similarity) for page, similarity in results if similarity >= floor]
    if not results:
        return []
    best = max(similarity for _, similarity in results)
    return [(page, similarity) for page, similarity in results if similarity >= best - margin]


def rrf_fuse(keyword_pages: list[str], semantic_pages: list[str], k: int = RRF_K):
    """[(page, очки, источник)] по убыванию очков. Найденные обоими поднимаются выше."""
    scores, sources = {}, {}
    for rank, page in enumerate(keyword_pages, start=1):
        scores[page] = scores.get(page, 0.0) + 1.0 / (k + rank)
        sources[page] = "keyword"
    for rank, page in enumerate(semantic_pages, start=1):
        scores[page] = scores.get(page, 0.0) + 1.0 / (k + rank)
        sources[page] = "both" if sources.get(page) == "keyword" else "semantic"
    order = sorted(scores, key=lambda page: scores[page], reverse=True)
    return [(page, scores[page], sources[page]) for page in order]


def _copy_context(context, **updates):
    # Не меняем объект на месте: точный результат лежит в кэше и используется повторно.
    if hasattr(context, "model_copy"):
        return context.model_copy(update=updates)
    import copy
    new_context = copy.copy(context)
    for key, value in updates.items():
        setattr(new_context, key, value)
    return new_context


def _semantic_results(db, query, size_values, brand, category):
    from app.services.semantic_search_service import semantic_search

    cache_key = f"semantic:{query}|{size_values}|{brand}|{category}"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached
    results = semantic_search(db, query, size_values=size_values, brand=brand,
                              category=category, limit=SEMANTIC_LIMIT)
    cache_service.set(cache_key, results, ttl=SEMANTIC_CACHE_TTL)
    return results


def load_cards(db, pages: list[str], size_values) -> dict:
    """Карточки для моделей, которые нашёл только смысловой поиск (тем же сериализатором, что точный)."""
    if not pages:
        return {}
    from sqlalchemy import func

    from app.db.models import Product
    from app.services.product_grouping_service import group_variants_by_model
    from app.services.product_serializer import serialize_model_card

    query = db.query(Product).filter(
        Product.is_active.is_(True),
        func.split_part(Product.product_url, "?", 1).in_(pages),
    )
    if size_values:
        query = query.filter(Product.size.in_(list(size_values)))
    cards = group_variants_by_model(query.order_by(Product.id).all())
    return {page_of(card.product.product_url): serialize_model_card(card) for card in cards}


def apply_hybrid(db, request, context, brand=None, category=None):
    """Точный результат → гибридный. При любой проблеме — точный результат без изменений."""
    if not is_enabled() or getattr(request, "offset", 0):
        return context
    query = getattr(request, "raw_query", None) or getattr(context, "query", "")
    if not needs_semantic(query, getattr(context, "search_strategy", None)):
        return context
    dialect = getattr(getattr(getattr(db, "bind", None), "dialect", None), "name", None)
    if dialect != "postgresql":   # тесты на SQLite / подставные объекты — только точный поиск
        return context

    from app.repositories.product_repository import size_variants
    size_values = size_variants(request.size) if getattr(request, "size", None) else None
    try:
        with request_timings.stage("search.semantic"):  # 15.10: замер (эмбеддинг + поиск по смыслу)
            semantic = filter_semantic(_semantic_results(db, query, size_values, brand, category))
    except Exception as error:
        logger.warning("Semantic search unavailable, keyword only: %s", error)
        return context


    keyword_items = list(context.items or [])
    items_by_page = {page_of(item.get("product_url")): item for item in keyword_items}
    fused = rrf_fuse(list(items_by_page), [page for page, _ in semantic])

    missing = [page for page, _, _ in fused if page not in items_by_page]
    with request_timings.stage("search.semantic"):  # карточки для найденных только по смыслу
        items_by_page.update(load_cards(db, missing, size_values))

    similarity_by_page = dict(semantic)
    final_items = []
    for page, _, source in fused:
        item = items_by_page.get(page)
        if item is None:
            continue
        similarity = similarity_by_page.get(page)
        final_items.append({**item, "source": source,
                            "similarity": round(similarity, 3) if similarity is not None else None})
        if len(final_items) >= request.limit:
            break

    updates = {"items": final_items}
    if not context.total_count and final_items:
        updates.update(total_count=len(final_items), matched_by="semantic", retrieval_mode="semantic")
    elif any(item["source"] != "keyword" for item in final_items):
        updates["retrieval_mode"] = "hybrid"
        # 09.10: точный нашёл 1, смысловой добавил 4 → клиенту говорили "нашли один", а показывали пять
        updates["total_count"] = max(context.total_count, len(final_items))
    return _copy_context(context, **updates)

def prefetch_query_vector(db, request, strategy) -> None:
    """16.10: начать считать вектор запроса В ФОНЕ, пока идёт точный поиск (−1–2 с на новых запросах).
    Те же условия, что у apply_hybrid: включено, первая страница, без фильтров цены/скидки, не точная модель/артикул, Postgres."""
    if not is_enabled() or getattr(request, "offset", 0):
        return
    if getattr(request, "max_price", None) or getattr(request, "discount_only", False):
        return                                  # с бюджетом / «только скидки» гибрид не используется
    query = getattr(request, "raw_query", None)
    if not query or not needs_semantic(query, strategy):
        return
    dialect = getattr(getattr(getattr(db, "bind", None), "dialect", None), "name", None)
    if dialect != "postgresql":
        return
    from app.services import embedding_client
    embedding_client.prefetch_query(query)