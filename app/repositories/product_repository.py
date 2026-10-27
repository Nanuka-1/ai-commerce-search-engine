import re
from sqlalchemy import and_, or_, cast, String
from sqlalchemy.orm import Session
from app.db.models import Product
from app.services.product_enrichment_service import (
    extract_model_family,
    extract_color,
)

CANDIDATE_SAFETY_LIMIT = 500

EDGE_PUNCTUATION = "?!.,;:()[]\"'«»„“”…"
WORD_CHAR = re.compile(r"\w")


def clean_query_tokens(q: str | None) -> list[str]:
    """Слова запроса без знаков по краям; одиночный знак — не слово.
    12.10: «როგორ ხარ ?» → «?» находил товар с «?» в названии (Nike AIR 7? BIKE SHORT)."""
    tokens = [token.strip(EDGE_PUNCTUATION) for token in (q or "").split()]
    return [token for token in tokens if WORD_CHAR.search(token)]


def deal_conditions(max_price: float | None = None, discount_only: bool = False, new_only: bool = False,
                    exclude_brands: list[str] | None = None) -> list:
    """U2.3 (12.10): «до N лари» и «только со скидкой» — фильтр в БАЗЕ (тогда и число найденных честное).
    Скидка = обычная (зачёркнутая) цена больше текущей — те же цены, что на карточке (−30%).
    21.10: «новинки» — список магазина (ingestion/collect_new_products.py → is_new);
    «другой бренд» — без брендов, уже показанных в разговоре."""
    conditions = []
    if max_price:
        conditions.append(Product.price <= max_price)
    if discount_only:
        conditions.append(and_(Product.regular_price.isnot(None), Product.regular_price > Product.price))
    if new_only:
        conditions.append(Product.is_new == True)
    if exclude_brands:
        conditions.append(Product.brand.notin_(exclude_brands))
    return conditions

# 20.10 (экзамен): «ქალის სარბენი ფეხსაცმელი 38» → 0 беговых: в женских названиях нет слова «სარბენი» (0 из 514),
# а беговые размечены в sport_type (28). Слово о виде спорта ищем и в названии, и в разметке.
SPORT_WORD_ROOTS = {
    "სარბენ": "running",
    "სირბილ": "running",
    "running": "running",
    "runner": "running",
}


def sport_type_for_token(token: str) -> str | None:
    lowered = token.lower()
    for root, sport in SPORT_WORD_ROOTS.items():
        if lowered.startswith(root):
            return sport
    return None


def token_condition(token: str):
    """Одно слово запроса: название / бренд / артикул / размер, а слово о спорте — ещё и sport_type."""
    conditions = [
        Product.name.ilike(f"%{token}%"),
        Product.brand.ilike(f"%{token}%"),
        Product.sku.ilike(f"%{token}%"),
        cast(Product.size, String).ilike(f"%{token}%"),
    ]
    sport = sport_type_for_token(token)
    if sport:
        conditions.append(Product.sport_type == sport)
    return or_(*conditions)
LETTER_SIZE_ALIASES = {
    "XXS": ["XXS", "2XS"],
    "XS": ["XS", "XS/S"],
    "S": ["S", "SM", "XS/S", "S/M"],
    "M": ["M", "MD", "S/M", "M/L"],
    "L": ["L", "LG", "M/L", "L/XL"],
    "XL": ["XL", "L/XL", "XL/XXL", "XL/2XL"],
    "XXL": ["XXL", "2XL", "XL/XXL", "XL/2XL"],
    "XXXL": ["XXXL", "3XL"],
}


def size_variants(size: str) -> list[str]:
    normalized = size.strip().upper().replace(",", ".")

    if normalized in LETTER_SIZE_ALIASES:
        return LETTER_SIZE_ALIASES[normalized]

    variants = [normalized]
    try:
        value = float(normalized)
    except ValueError:
        return variants

    if value.is_integer():
        number = int(value)
        variants += [f"{number - 1}-{number}", f"{number}-{number + 1}"]

    return variants


def size_condition(size: str):
    return Product.size.in_(size_variants(size))


CATEGORIES_INCLUDING_UNISEX = {"მამაკაც", "ქალ"}
UNISEX_CATEGORY = "unisex"


def category_condition(category: str):
    patterns = [category]
    if category in CATEGORIES_INCLUDING_UNISEX:
        patterns.append(UNISEX_CATEGORY)
    return or_(*[Product.category_slug.ilike(f"%{pattern}%") for pattern in patterns])

def search_exact_model_products(
    db: Session,
    model_hint: str,
    brand: str | None = None,
    size: str | None = None,
    category: str | None = None,
    style_group: str | None = None,
    limit: int = 200,
):
    query = db.query(Product).filter(
        Product.name.ilike(f"%{model_hint}%"),
        Product.is_active == True,
    )

    if brand:
        query = query.filter(Product.brand.ilike(f"%{brand}%"))

    if size:
        query = query.filter(size_condition(size))

    if category:
        query = query.filter(category_condition(category))

    if style_group:
        query = query.filter(Product.style_group == style_group)

    total_count = query.count()
    items = query.limit(limit).all()

    return items, total_count


def search_same_brand_size_products(
    db: Session,
    brand: str,
    size: str | None = None,
    category: str | None = None,
    style_group: str | None = None,
    limit: int = 200,
):
    query = db.query(Product).filter(
        Product.brand.ilike(f"%{brand}%"),
        Product.is_active == True,
    )

    if size:
        query = query.filter(size_condition(size))

    if category:
        query = query.filter(category_condition(category))

    if style_group:
        query = query.filter(Product.style_group == style_group)

    total_count = query.count()
    items = query.limit(limit).all()

    return items,total_count



def get_products_by_query(
    db: Session,
    q: str,
    size: str | None = None,
    category: str | None = None,
    style_group: str | None = None,
    brand: str | None = None,
    limit: int = 5,
    offset: int = 0,
    max_price: float | None = None,
    discount_only: bool = False,
    new_only: bool = False,
    exclude_brands: list[str] | None = None,
):
    tokens = [
        token
        for token in clean_query_tokens(q)
        if not size or token.upper().replace(",", ".") not in size_variants(size)
    ]

    if not tokens and size:
        tokens = [brand] if brand else []

    if not tokens:
        return [], 0

    deals = deal_conditions(max_price, discount_only, new_only, exclude_brands)

    and_filters = [token_condition(token) for token in tokens]

    strict_query = db.query(Product).filter(and_(*and_filters))
    strict_query = strict_query.filter(Product.is_active == True)


    if size:
        strict_query = strict_query.filter(size_condition(size))

    if category:
        strict_query = strict_query.filter(category_condition(category))

    if style_group:
        strict_query = strict_query.filter(Product.style_group == style_group)

    if deals:
        strict_query = strict_query.filter(*deals)

    strict_total_count = strict_query.count()

    if strict_total_count > 0:
        fetch_limit = max(limit, CANDIDATE_SAFETY_LIMIT)
        strict_results = strict_query.limit(fetch_limit).all()

        return strict_results, strict_total_count

    or_filters = [token_condition(token) for token in tokens]

    fallback_query = db.query(Product).filter(or_(*or_filters))
    fallback_query = fallback_query.filter(Product.is_active == True)

    if size:
        fallback_query = fallback_query.filter(size_condition(size))

    if category:
        fallback_query = fallback_query.filter(category_condition(category))

    if style_group:
        fallback_query = fallback_query.filter(Product.style_group == style_group)

    if brand:
        fallback_query = fallback_query.filter(
            Product.brand.ilike(f"%{brand}%")
        )

    if deals:
        fallback_query = fallback_query.filter(*deals)

    fallback_total_count = fallback_query.count()

    fetch_limit = max(limit, CANDIDATE_SAFETY_LIMIT)
    fallback_results = fallback_query.limit(fetch_limit).all()

    return fallback_results, fallback_total_count


def get_products_by_size(
    db: Session,
    size: str | None = None,
    category: str | None = None,
    limit: int = 200,
    max_price: float | None = None,
    discount_only: bool = False,
    new_only: bool = False,
    exclude_brands: list[str] | None = None,
):
    query = db.query(Product).filter(Product.is_active == True)

    if size:
        query = query.filter(size_condition(size))

    if category:
        query = query.filter(category_condition(category))

    deals = deal_conditions(max_price, discount_only, new_only, exclude_brands)
    if deals:
        query = query.filter(*deals)

    total_count = query.count()
    results = query.limit(limit).all()

    return results, total_count

def create_product(db: Session, product_data):
    model_family = extract_model_family(product_data.name)
    color = extract_color(product_data.name)

    product = Product(
        sku=product_data.sku,
        name=product_data.name,
        brand=product_data.brand,
        price=product_data.price,
        category_slug=product_data.category_slug,
        size=product_data.size,
        product_url=product_data.product_url,
        image_url=product_data.image_url,

        style_group=product_data.style_group,
        sport_type=product_data.sport_type,
        usage_type=product_data.usage_type,

        model_family=model_family,
        color=color,
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    return product

def get_product_by_sku(db: Session, sku: str):
    return db.query(Product).filter(
        Product.sku == sku,
        Product.is_active == True,
    ).first()

# 26.10 (этап 3, п.2): ссылка на товар от клиента → все размеры ЭТОЙ модели (точное совпадение адреса).
# В базе адрес варианта — «<страница>?size=36». LIKE со «?» на конце: «…-25» не захватит соседнюю «…-250».
def get_products_by_page(db: Session, page: str):
    escaped = page.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return db.query(Product).filter(
        or_(Product.product_url == page, Product.product_url.like(f"{escaped}?%", escape="\\")),
        Product.is_active == True,
    ).all()