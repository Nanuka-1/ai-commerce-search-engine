from app.services.product_grouping_service import ModelCard, page_key


def serialize_product(product) -> dict:
    return {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "brand": product.brand,
        "price": product.price,
        "size": product.size,
        # Раньше этих полей не было: response_builder ждал product_url/available,
        # но получал словарь без них — клиент оставался без ссылки на товар.
        "product_url": getattr(product, "product_url", None),
        "available": getattr(product, "is_active", None),
        "category_slug": getattr(product, "category_slug", None),
                "color": getattr(product, "color", None),
        "image_url": getattr(product, "image_url", None),          # фото для карточки на странице
        "regular_price": getattr(product, "regular_price", None),  # зачёркнутая цена / скидка
    }
    


def serialize_products(products) -> list[dict]:
    return [
        serialize_product(product)
        for product in products
    ]


def serialize_model_card(card: ModelCard) -> dict:
    data = serialize_product(card.product)
    data["sizes"] = card.sizes
    data["price_from"] = card.price_from
    if len(card.sizes) > 1:
        # Ссылка на модель целиком, а не на один размер — клиент выберет размер на сайте.
        data["product_url"] = page_key(card.product)
    return data


def serialize_model_cards(cards: list[ModelCard]) -> list[dict]:
    return [serialize_model_card(card) for card in cards]