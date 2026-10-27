import re

from app.services.product_enrichment_service import MODEL_FAMILIES


def normalize_search_query(query: str) -> str:
    return query.strip().lower()


# Бренды каталога (SQL 02.10: 11 брендов) + New Balance — в каталоге его нет,
# но распознаём, чтобы честно ответить "такого бренда нет, вот похожее" (brand_fallback).
# Ключ — каноническое имя, которое уходит в поиск; значения — английское и ОДНО основное
# грузинское написание. Опечатки и падежные окончания (ნაიკის, adidsa) НЕ перечисляем —
# их распознаёт _is_close() автоматически.
BRAND_ALIASES = {
    "nike": ["nike", "ნაიკი"],
    "adidas": ["adidas", "ადიდასი"],
    "puma": ["puma", "პუმა"],
    "under armour": ["under armour", "ანდერ არმორი"],
    "reebok": ["reebok", "რიბოკი"],
    "crocs": ["crocs", "კროქსი"],
    "speedo": ["speedo", "სპიდო"],
    "garlando": ["garlando", "გარლანდო"],
    "weider": ["weider", "ვეიდერი"],
    "asics": ["asics", "ასიქსი"],
    "giant": ["giant", "ჯაიანტი"],
    "new balance": ["new balance", "ნიუ ბალანსი"],
}

KNOWN_BRANDS = list(BRAND_ALIASES)

_ALIASES_LONGEST_FIRST = sorted(
    ((brand, alias) for brand, aliases in BRAND_ALIASES.items() for alias in aliases),
    key=lambda pair: len(pair[1]),
    reverse=True,
)


# Единый список моделей со скрапером (product_enrichment_service.MODEL_FAMILIES)
MODEL_KEYWORDS = MODEL_FAMILIES

_MODELS_LONGEST_FIRST = sorted(
    ((model, model) for model in MODEL_KEYWORDS),
    key=lambda pair: len(pair[1]),
    reverse=True,
)


def _edit_distance(a: str, b: str) -> int:
    """Сколько правок (вставка, удаление, замена, перестановка соседних букв) отделяет a от b."""
    prev2 = None
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        prev2, prev = prev, cur
    return prev[len(b)]


def _is_close(word: str, alias: str) -> bool:
    """Одна опечатка или падежное окончание: adidsa→adidas, ნაიკის→ნაიკი, under armor→under armour.
    Для коротких (4 буквы) — только перестановка соседних букв: nkie→nike, но nice≠nike."""
    if len(alias) < 4 or abs(len(word) - len(alias)) > 1:
        return False
    if len(alias) == 4:
        return sorted(word) == sorted(alias) and _edit_distance(word, alias) == 1
    return _edit_distance(word, alias) <= 1


def _find_close_alias(normalized_query: str, aliases_longest_first) -> str | None:
    """Ищет в запросе слово или пару слов, отличающиеся от написания одной правкой (_is_close).
    aliases_longest_first — пары (что вернуть, написание), длинные написания первыми."""
    words = re.findall(r"[^\W\d_]+", normalized_query)
    candidates = words + [f"{first} {second}" for first, second in zip(words, words[1:])]
    for candidate in candidates:
        for key, alias in aliases_longest_first:
            if alias.count(" ") == candidate.count(" ") and _is_close(candidate, alias):
                return key
    return None


def extract_brand_from_query(query: str) -> str | None:
    normalized_query = normalize_search_query(query)

    # 1) Точное написание (как раньше); длинные первыми, чтобы "under armour" не перехватывалось.
    for brand, alias in _ALIASES_LONGEST_FIRST:
        if alias in normalized_query:
            return brand

    # 2) Опечатки и окончания — по отдельным словам и парам слов (для двухсловных брендов).
    return _find_close_alias(normalized_query, _ALIASES_LONGEST_FIRST)


def extract_model_hint_from_query(query: str) -> str | None:
    normalized_query = normalize_search_query(query)

    # Дефис как пробел — так же, как в названиях товаров (extract_model_family): "rs-x" -> "rs x".
    normalized_query = normalized_query.replace("-", " ")

    # 1) Точное написание (как раньше).
    for model in MODEL_KEYWORDS:
        if model in normalized_query:
            return model

    # 2) Опечатка в модели: pegasos -> pegasus, gazele -> gazelle, air froce -> air force.
    return _find_close_alias(normalized_query, _MODELS_LONGEST_FIRST)


def extract_usage_type_from_query(query: str) -> str | None:
    normalized_query = normalize_search_query(query)

    if "running" in normalized_query or "სირბილ" in normalized_query or "სარბენ" in normalized_query:
        return "running"

    if "football" in normalized_query:
        return "football"

    if "basketball" in normalized_query or "კალათბურთ" in normalized_query:
        return "basketball"

    if "casual" in normalized_query:
        return "casual"

    return None