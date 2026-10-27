"""
Бегущая строка / промо-блок чата (шаг F3).

ЧТО показывать — решает файл app/config/promo.json (маркетинг меняет его без программиста):
  "mode": "auto_discounts" — самые большие скидки сегодня (из regular_price vs price, данные с сайта);
  "mode": "fresh_drops"    — СВЕЖИЕ снижения цен: подешевели в последнем завершённом прогоне скрапера
                             (история product_changes), подпись с датой прогона — «с 9 октября»;
  "mode": "manual"         — ровно те модели, что перечислены в "manual_pages"
                             (ссылки на страницы товаров topsport.ge, в нужном порядке);
  "limit"                  — сколько моделей в строке;
  "min_discount_percent"   — для auto: скидка не меньше (%);
  "min_drop_percent"       — для fresh_drops: цена снизилась не меньше чем на (%);
  "title"                  — заголовок на ka / en;
  "sale_url"               — куда ведёт кнопка «🔥 ფასდაკლებები» (страница распродажи сайта, ka / en).
Файл перечитывается при каждом обновлении кэша (10 мин) — перезапуск сервера не нужен.

Честность: показываем только активные товары и реальные цены с сайта.
"""
import json
from pathlib import Path

from sqlalchemy import text

from app.db.models import Product
from app.services import cache_service
from app.services.product_grouping_service import page_key
from app.services.translations import translate

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "promo.json"
CACHE_KEY = "promo:ticker"
CACHE_TTL = 600

DEFAULT_CONFIG = {
    "mode": "auto_discounts",
    "limit": 8,
    "min_discount_percent": 20,
    "min_drop_percent": 10,
    "manual_pages": [],
    "title": {"ka": "🔥 დღის ფასდაკლებები", "en": "🔥 Today's deals"},
    "sale_url": {"ka": "https://topsport.ge/ka/products/sale", "en": "https://topsport.ge/en/products/sale"},
}


def load_config(path: Path = CONFIG_PATH) -> dict:
    """Ошибка в файле не должна ломать чат — тогда берём настройки по умолчанию."""
    try:
        return {**DEFAULT_CONFIG, **json.loads(path.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return dict(DEFAULT_CONFIG)


def discount_percent(price, regular_price) -> int:
    if not price or not regular_price or regular_price <= price:
        return 0
    return round((1 - price / regular_price) * 100)


def _promo_item(product) -> dict:
    return {
        "name": product.name,
        "brand": product.brand,
        "price": product.price,
        "regular_price": product.regular_price,
        "discount_percent": discount_percent(product.price, product.regular_price),
        "product_url": page_key(product),          # страница модели, размер клиент выберет на сайте
        "image_url": getattr(product, "image_url", None),
    }


def _size_key(size) -> tuple:
    try:
        return (0, float(str(size).replace(",", ".")), "")
    except ValueError:
        return (1, 0.0, str(size))


def _sizes_by_page(products) -> dict:
    """Размеры модели в подборке (только варианты, которые попали в скидку/снижение)."""
    sizes = {}
    for product in products:
        if product.size:
            sizes.setdefault(page_key(product), set()).add(str(product.size))
    return {page: sorted(values, key=_size_key) for page, values in sizes.items()}


def _best_variant_by_page(products) -> dict:
    """Один вариант на модель (страницу) — с самой большой скидкой."""
    best = {}
    for product in products:
        key = page_key(product)
        current = best.get(key)
        if current is None or discount_percent(product.price, product.regular_price) > \
                discount_percent(current.price, current.regular_price):
            best[key] = product
    return best


def select_auto_deals(db, limit: int, min_discount_percent: int) -> list[dict]:
    rows = (db.query(Product)
            .filter(Product.is_active.is_(True),
                    Product.regular_price.isnot(None),
                    Product.regular_price > Product.price)
            .all())
    best = _best_variant_by_page(rows).values()
    sizes = _sizes_by_page(rows)
    deals = [p for p in best if discount_percent(p.price, p.regular_price) >= min_discount_percent]
    deals.sort(key=lambda p: (-discount_percent(p.price, p.regular_price), p.name or ""))
    return [{**_promo_item(p), "sizes": sizes.get(page_key(p), [])} for p in deals[:limit]]


# Последний ЗАВЕРШЁННЫЙ прогон: незавершённый (finished_at пуст) мог пройти не все товары.
# 12.10: прогон 3 (05.10) дал 6 976 «снижений» — след правки скрапера (п.46), не скидки; берём только последний.
FRESH_DROPS_SQL = text("""
    SELECT r.started_at AS since, pc.sku, pc.old_price, pc.new_price
    FROM product_changes pc
    JOIN scrape_runs r ON r.id = pc.run_id
    WHERE r.id = (SELECT MAX(id) FROM scrape_runs WHERE finished_at IS NOT NULL)
      AND pc.field = 'price'
      AND pc.old_price IS NOT NULL AND pc.new_price IS NOT NULL
      AND pc.new_price < pc.old_price
""")


def drop_percent(old_price, new_price) -> int:
    if not old_price or not new_price or new_price >= old_price:
        return 0
    return round((old_price - new_price) / old_price * 100)


def select_fresh_drops(db, limit: int, min_drop_percent: int) -> tuple[list[dict], str | None]:
    """(товары, дата прогона «YYYY-MM-DD»). Честно: только активные и только если цена с тех пор не менялась."""
    rows = db.execute(FRESH_DROPS_SQL).mappings().all()
    if not rows:
        return [], None
    since = str(rows[0]["since"])[:10]
    drops = {row["sku"]: row for row in rows}

    products = db.query(Product).filter(Product.sku.in_(list(drops)), Product.is_active.is_(True)).all()
    best = {}
    still_dropped = []
    for product in products:
        drop = drops[product.sku]
        if product.price != drop["new_price"]:
            continue                       # цена снова изменилась после прогона — «свежим снижением» не считаем
        percent = drop_percent(drop["old_price"], drop["new_price"])
        if percent < min_drop_percent:
            continue
        still_dropped.append(product)
        key = page_key(product)
        if key not in best or percent > best[key][1]:
            best[key] = (product, percent, drop["old_price"])

    ordered = sorted(best.values(), key=lambda entry: (-entry[1], entry[0].name or ""))
    sizes = _sizes_by_page(still_dropped)
    items = [{**_promo_item(product), "old_price": old_price, "drop_percent": percent,
              "sizes": sizes.get(page_key(product), [])}
             for product, percent, old_price in ordered[:limit]]
    return items, since


DEALS_CANDIDATES = 60     # подборка целиком (пачки по 5 — срезы из неё)


def build_deals_response(db, user_id: str, language: str, limit: int = 5, offset: int = 0,
                         max_price: float | None = None, config: dict | None = None) -> dict:
    """Подборка скидок для чата и кнопки виджета (пачками: offset 0, 5, 10…).
    Сначала СВЕЖИЕ снижения цен (с датой прогона), иначе самые большие скидки. Без LLM, только данные базы."""
    config = config or load_config()
    language = language if language in ("ka", "en") else "ka"
    items, since = select_fresh_drops(db, DEALS_CANDIDATES, int(config.get("min_drop_percent", 10)))
    # на карточке «было → стало»: если у сайта нет зачёркнутой цены — цена до снижения
    items = [{**item, "regular_price": item.get("regular_price") or item.get("old_price")} for item in items]
    key = "deals_fresh"
    if not items:
        items = select_auto_deals(db, DEALS_CANDIDATES, int(config.get("min_discount_percent", 0)))
        key, since = "deals_top", None
    if max_price:
        items = [item for item in items if item.get("price") and item["price"] <= max_price]

    page = items[offset: offset + limit]
    if not page:
        key = "deals_none" if offset == 0 else "deals_no_more"
    elif offset > 0:
        key = "deals_more"
    date = f"{since[8:10]}.{since[5:7]}" if since else ""
    sale_url = (config.get("sale_url") or {}).get(language) or DEFAULT_CONFIG["sale_url"][language]
    return {
        "type": "deals",
        "message": translate(key, language).format(date=date),
        "data": {"user_id": user_id, "results": {
            "items": page, "since": since, "site_search_url": sale_url,
            "offset": offset, "limit": limit, "total": len(items), "max_price": max_price,
            "has_more": offset + limit < len(items),
        }},
    }


def select_manual(db, pages: list[str], limit: int) -> list[dict]:
    pages = [page.split("?")[0].strip() for page in pages if page and page.strip()]
    if not pages:
        return []
    rows = db.query(Product).filter(Product.is_active.is_(True)).all()
    best = _best_variant_by_page([p for p in rows if page_key(p) in set(pages)])
    # порядок — как у маркетинга в файле; снятые с продажи модели просто пропускаются
    return [_promo_item(best[page]) for page in pages if page in best][:limit]


def get_ticker(db, language: str = "ka", config: dict | None = None) -> dict:
    config = config or load_config()
    language = language if language in ("ka", "en") else "ka"

    mode = config.get("mode")
    limit = int(config.get("limit", 8))
    cache_key = f"{CACHE_KEY}:{mode}"            # смена режима в файле не отдаёт старый кэш
    cached = cache_service.get(cache_key)
    if cached is None:
        since = None
        if mode == "manual":
            items = select_manual(db, config.get("manual_pages", []), limit)
        elif mode == "fresh_drops":
            items, since = select_fresh_drops(db, limit, int(config.get("min_drop_percent", 10)))
        else:
            items = select_auto_deals(db, limit, int(config.get("min_discount_percent", 0)))
        cached = {"items": items, "since": since}
        cache_service.set(cache_key, cached, ttl=CACHE_TTL)

    title = (config.get("title") or {}).get(language) or DEFAULT_CONFIG["title"][language]
    sale_url = (config.get("sale_url") or {}).get(language) or DEFAULT_CONFIG["sale_url"][language]
    return {"title": title, "sale_url": sale_url, "mode": mode,
            "since": cached["since"],                # fresh_drops: дата прогона — «подешевели с …»
            "items": cached["items"]}