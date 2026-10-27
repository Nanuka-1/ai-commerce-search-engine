from app.db.session import SessionLocal
from app.db.models import Product
from app.services.product_intent_service import extract_product_intent, classify_product_type
from app.services.product_enrichment_service import extract_model_family, extract_color

BATCH_SIZE = 500


def backfill_classification(db=None):
    owns_session = db is None
    if db is None:
        db = SessionLocal()

    products = db.query(Product).all()
    total = len(products)
    print(f"Найдено товаров для бэкфилла: {total}")

    updated_count = 0
    for i, product in enumerate(products, start=1):
        base_sku = product.sku.rsplit("-", 1)[0] if product.sku else ""
        classification_text = " ".join(
            part for part in [product.name, product.brand, base_sku] if part
        )

        product_intent = extract_product_intent(classification_text, product.category_slug)
        product_type = classify_product_type(product.category_slug)

        product.product_type = product_type.value
        product.style_group = product_intent.style_group.value if product_intent and product_intent.style_group else None
        product.sport_type = product_intent.sport_type.value if product_intent and product_intent.sport_type else None
        product.usage_type = product_intent.usage_type.value if product_intent else None
        product.model_family = extract_model_family(product.name or "")
        product.color = extract_color(product.name or "")

        updated_count += 1

        if owns_session and i % BATCH_SIZE == 0:
            db.commit()
            print(f"…обработано {i} из {total}")

    db.commit()
    print(f"Готово. Обновлено товаров: {updated_count}")

    if owns_session:
        db.close()

    return updated_count


if __name__ == "__main__":
    backfill_classification()