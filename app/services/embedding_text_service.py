
"""
Текст карточки модели для смыслового поиска (embeddings, шаг 3.5).

Gemini "понимает" только то, что есть в тексте. Название у многих товаров общее
("Nike მამაკაცის სპორტული ფეხსაცმელი"), поэтому к названию добавляем всё, что мы
знаем о товаре из наших данных: пол, тип, вид спорта, модель, цвет — с английскими
словами-якорями, чтобы запросы на обоих языках попадали рядом.

Размер и цену НЕ кладём: они меняются и фильтруются точными правилами.
Одна карточка = одна страница сайта (модель), берём её представителя-вариант.
"""
import hashlib

GENDER_BY_CATEGORY_ROOT = [
    ("ბავშვ", "kids"),
    ("ქალ", "women"),
    ("მამაკაც", "men"),
    ("Unisex", "unisex"),
]

PRODUCT_TYPE_WORDS = {
    "footwear": "shoes, footwear",
    "clothing": "clothing, apparel",
    "accessory": "accessory",
    "equipment": "sports equipment",
    "nutrition": "sports nutrition",
}

SPORT_WORDS = {
    "running": "running",
    "casual": "casual, lifestyle, everyday",
    "basketball": "basketball",
    "football": "football, soccer",
}


def _gender(category_slug: str | None) -> str | None:
    if not category_slug:
        return None
    for root, gender in GENDER_BY_CATEGORY_ROOT:
        if root in category_slug:
            return gender
    return None


def build_embedding_text(product) -> str:
    """product — объект/строка products (нужны поля name, brand, category_slug,
    product_type, sport_type, model_family, color)."""
    parts = [(getattr(product, "name", None) or "").strip()]

    facts = [
        ("brand", getattr(product, "brand", None)),
        ("for", _gender(getattr(product, "category_slug", None))),
        ("type", PRODUCT_TYPE_WORDS.get(getattr(product, "product_type", None) or "")),
        ("sport", SPORT_WORDS.get(getattr(product, "sport_type", None) or "")),
        ("model", getattr(product, "model_family", None)),
        ("color", getattr(product, "color", None)),
    ]
    parts += [f"{label}: {value}" for label, value in facts if value]
    return " | ".join(part for part in parts if part)


def text_hash(text: str) -> str:
    """Отпечаток текста: если он не изменился, embedding пересчитывать не нужно."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()