"""
Карточка модели: варианты одной страницы сайта (модель в разных размерах) склеиваются в одну.

Без этого запрос без размера ("pegasus", "crocs") показывает 2–3 модели вместо 10:
выдача забита размерами одной модели (замер measure_card_duplicates.py, 02.10).
С размером ("nike 42") на модель и так одна строка — группировка ничего не меняет.

Порядок карточек = порядок лучшего варианта после rank_products (ранжирование не трогаем).
"""
from dataclasses import dataclass, field

SIZE_LETTER_ORDER = ["XXS", "2XS", "XS", "S", "M", "L", "XL", "XXL", "2XL", "XXXL", "3XL"]


@dataclass
class ModelCard:
    product: object                      # лучший по рейтингу вариант — представляет модель
    sizes: list[str] = field(default_factory=list)
    price_from: float | None = None


def page_key(product) -> str:
    url = getattr(product, "product_url", None) or ""
    return url.split("?")[0] or getattr(product, "sku", None) or str(id(product))


def _size_sort_key(size: str):
    head = size.split("-")[0]            # Crocs "41-42" сортируем по первому числу
    try:
        return (0, float(head.replace(",", ".")), size)
    except ValueError:
        pass
    upper = size.upper()
    if upper in SIZE_LETTER_ORDER:
        return (1, SIZE_LETTER_ORDER.index(upper), size)
    return (2, 0, size)


def group_variants_by_model(products) -> list[ModelCard]:
    cards: dict[str, ModelCard] = {}
    for product in products:
        key = page_key(product)
        card = cards.get(key)
        if card is None:
            card = cards[key] = ModelCard(product=product)

        size = getattr(product, "size", None)
        price = getattr(product, "price", None)
        if size and size not in card.sizes:
            card.sizes.append(size)
        if price is not None and (card.price_from is None or price < card.price_from):
            card.price_from = price

    for card in cards.values():
        card.sizes.sort(key=_size_sort_key)
    return list(cards.values())