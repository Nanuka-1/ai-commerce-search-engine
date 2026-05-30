from sqlalchemy import and_, or_, cast, String
from sqlalchemy.orm import Session
from app.db.models import Product
from app.services.product_enrichment_service import (
    extract_model_family,
    extract_color,
)

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
        Product.name.ilike(f"%{model_hint}%")
    )

    if brand:
        query = query.filter(Product.brand.ilike(f"%{brand}%"))

    if size:
        query = query.filter(Product.size == size)

    if category:
        query = query.filter(Product.category_slug.ilike(f"%{category}%"))

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
        Product.brand.ilike(f"%{brand}%")
    )

    if size:
        query = query.filter(Product.size == size)

    if category:
        query = query.filter(Product.category_slug.ilike(f"%{category}%"))

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
):
    tokens = [
        token
        for token in q.split()
        if not size or token != size
    ]

    if not tokens and size:
        tokens = [brand] if brand else []

    if not tokens:
        return [], 0

    and_filters = [
        or_(
            Product.name.ilike(f"%{token}%"),
            Product.brand.ilike(f"%{token}%"),
            Product.sku.ilike(f"%{token}%"),
            cast(Product.size, String).ilike(f"%{token}%"),
        )
        for token in tokens
    ]

    strict_query = db.query(Product).filter(and_(*and_filters))

    if size:
        strict_query = strict_query.filter(Product.size == size)

    if category:
        strict_query = strict_query.filter(Product.category_slug.ilike(f"%{category}%"))

    if style_group:
        strict_query = strict_query.filter(Product.style_group == style_group)

    strict_total_count = strict_query.count()

    if strict_total_count > 0:
        strict_results = strict_query.limit(200).all()

        return strict_results, strict_total_count

    or_filters = [
        or_(
            Product.name.ilike(f"%{token}%"),
            Product.brand.ilike(f"%{token}%"),
            Product.sku.ilike(f"%{token}%"),
            cast(Product.size, String).ilike(f"%{token}%"),
        )
        for token in tokens
    ]

    fallback_query = db.query(Product).filter(or_(*or_filters))

    if size:
        fallback_query = fallback_query.filter(Product.size == size)

    if category:
        fallback_query = fallback_query.filter(Product.category_slug.ilike(f"%{category}%"))

    if style_group:
        fallback_query = fallback_query.filter(Product.style_group == style_group)

    if brand:
        fallback_query = fallback_query.filter(
            Product.brand.ilike(f"%{brand}%")
        )

    fallback_total_count = fallback_query.count()

    fallback_results = fallback_query.limit(200).all()

    return fallback_results, fallback_total_count


def get_products_by_size(
    db: Session,
    size: str,
    category: str | None = None,
    limit: int = 200,
):
    query = db.query(Product).filter(Product.size == size)

    if category:
        query = query.filter(Product.category_slug.ilike(f"%{category}%"))

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
    return db.query(Product).filter(Product.sku == sku).first()