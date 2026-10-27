from app.db.models import Product
from app.schemas.product_classification import ProductType, StyleGroup, SportType, UsageType
from ingestion.backfill_classification import backfill_classification


def _make_product(db, **overrides):
    defaults = dict(
        sku="TESTSKU-42",
        name="Nike Air Max",
        brand="Nike",
        price=100.0,
        category_slug="მამაკაცი, მამაკაცის ფეხსაცმელი",
        size="42",
        is_active=True,
    )
    defaults.update(overrides)
    defaults.setdefault("product_url", f"https://topsport.ge/product/{defaults['sku']}")

    product = Product(**defaults)
    db.add(product)
    db.flush()
    return product


def test_backfill_fills_null_classification_fields(db):
    product = _make_product(db)
    assert product.product_type is None

    updated_count = backfill_classification(db)

    db.refresh(product)
    assert updated_count == 1
    assert product.product_type == ProductType.FOOTWEAR.value


def test_backfill_uses_base_sku_for_keyword_match(db):
    product = _make_product(
        db, sku="PRED-99-40", name="Adidas Predator", brand="Adidas"
    )

    backfill_classification(db)

    db.refresh(product)
    assert product.style_group == StyleGroup.FOOTBALL_BOOTS.value
    assert product.sport_type == SportType.FOOTBALL.value
    assert product.usage_type == UsageType.PERFORMANCE.value