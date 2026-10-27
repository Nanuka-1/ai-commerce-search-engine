import re

from app.services.product_enrichment_service import COLOR_KEYWORDS, VERSIONED_MODELS


PRICE_PREFIXES = (
    "price",
    "how much is",
    "what is the price of",
    "რა ღირს",
)

GREETING_WORDS = {
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
    "გამარჯობა",
    "გაუმარჯოს",
    # 09.10: живой тест — "მოგესალმებით" ушло в поиск и показало случайные товары
    "მოგესალმებით",
    "გამარჯობათ",
    "სალამი",
    "ჰაი",
    "დილა მშვიდობისა",
    "საღამო მშვიდობისა",
    "hello there",
    "good day",
}

CATEGORY_KEYWORDS = {
    "men": "men",
    "male": "men",
    "man": "men",
    "მამაკაცი": "men",
    "მამაკაცის": "men",
    # 20.10 (экзамен): формы, которые пишут клиенты — «კაცის სარბენი 42» поиск не понимал как мужское
    "მამაკაცისთვის": "men",
    "კაცი": "men",
    "კაცის": "men",
    "კაცისთვის": "men",


    "women": "women",
    "woman": "women",
    "female": "women",
    "ქალი": "women",
    "ქალის": "women",
    # 20.10: «…36 ზომა ქალისთვის» → среди 5 попалась детская модель
    "ქალისთვის": "women",
    "ქალებისთვის": "women",


    "kids": "kids",
    "kid": "kids",
    "child": "kids",
    "children": "kids",
    "ბავშვი": "kids",
    "ბავშვის": "kids",
    # 20.10: «ბიჭის / გოგოს» (для мальчика / девочки) — в каталоге только «ბავშვის» (п.119)
    "ბავშვისთვის": "kids",
    "ბავშვებისთვის": "kids",
    "ბიჭი": "kids",
    "ბიჭის": "kids",
    "ბიჭისთვის": "kids",
    "გოგო": "kids",
    "გოგოს": "kids",
    "გოგოსთვის": "kids",
    "boy": "kids",
    "boys": "kids",
    "girl": "kids",
    "girls": "kids",
}

# Корни грузинских названий категорий, как их пишет скрапер в category_slug
# (например "მამაკაცი, მამაკაცის ფეხსაცმელი"). Проверено SQL 30.09:
# მამაკაც=5810, ქალ=4711, ბავშვ=1112 активных товаров.
CATEGORY_DB_SLUGS = {
    "men": "მამაკაც",
    "women": "ქალ",
    "kids": "ბავშვ",
}


SKU_PATTERN = re.compile(r"^(?=.*\d)[A-Z0-9]+(?:-[A-Z0-9._]+)*$", re.IGNORECASE)

def map_category_to_db_slug(category: str | None) -> str | None:
    if category is None:
        return None

    return CATEGORY_DB_SLUGS.get(category)

def normalize_text(message: str) -> str:
    return re.sub(r"\s+", " ", message.strip().lower())


GREETING_EDGE = "!.?,;:)( 👋🙂😊"


def is_greeting(message: str) -> bool:
    """22.10: приветствие — только если КРОМЕ него ничего нет («გამარჯობა!», «hello there»).
    «გამარჯობა + вопрос» — не приветствие: вопрос отвечаем (strip_greeting)."""
    normalized = normalize_text(message).strip(GREETING_EDGE)
    return normalized in GREETING_WORDS


def strip_greeting(message: str) -> str:
    """«გამარჯობა, ქალის ქურთუკი M» → «ქალის ქურთუკი M»; без приветствия — как есть; только приветствие → ""."""
    text = (message or "").strip()
    lowered = text.lower()
    for word in sorted(GREETING_WORDS, key=len, reverse=True):   # длинные первыми: «გამარჯობათ» раньше «გამარჯობა»
        if lowered.startswith(word) and (len(lowered) == len(word) or not lowered[len(word)].isalnum()):
            return text[len(word):].strip(GREETING_EDGE)
    return text


def is_price_check(message: str) -> bool:
    normalized = normalize_text(message)
    return any(
        normalized == prefix or normalized.startswith(prefix + " ")
        for prefix in PRICE_PREFIXES
    )


def extract_price_sku(message: str) -> str | None:
    normalized = normalize_text(message)

    for prefix in PRICE_PREFIXES:
        if normalized.startswith(prefix):
            value = normalized[len(prefix):].strip()

            #  აუცილებელი შემოწმება რომ სკუ არ არის
            if value and is_sku(value):
                return value.upper()

            return None

    return None

def extract_price_query(message: str) -> str | None:
    normalized = normalize_text(message)

    for prefix in PRICE_PREFIXES:
        if normalized == prefix:
            return None

        if normalized.startswith(prefix + " "):
            query = normalized[len(prefix):].strip()
            return query if query else None

    return None


MIN_SKU_LENGTH = 6   # 09.10: "33"/"42" считались артикулом → "SKU не найден"; реальные: 31241503, CW2288-111


def is_sku(message: str) -> bool:
    normalized = message.strip()
    if len(normalized) < MIN_SKU_LENGTH:
        return False

    return bool(SKU_PATTERN.match(normalized))


def detect_intent(message: str) -> str:
    if not message.strip():
        return "empty"

    if is_greeting(message):
        return "greeting"

    if is_price_check(message):
        return "price_check"

    if is_sku(message):
        return "sku_search"

    return "product_search"

MIN_SHOE_SIZE = 20
MAX_SHOE_SIZE = 55

LETTER_SIZE_CANONICAL = {
    "XXS": "XXS", "2XS": "XXS",
    "XS": "XS",
    "S": "S",
    "M": "M",
    "L": "L",
    "XL": "XL",
    "XXL": "XXL", "2XL": "XXL",
    "XXXL": "XXXL", "3XL": "XXXL",
}


def _format_shoe_size(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


def extract_size_from_query(query: str) -> str | None:
    numeric_size = None
    for match in re.finditer(r"\b\d+(?:[.,]\d+)?\b", query):
        previous_word = re.search(r"([A-Za-z]+)\s*$", query[:match.start()])
        if previous_word and match.group(0) in VERSIONED_MODELS.get(previous_word.group(1).lower(), ()):
            continue  # "pegasus 41", "ultraboost 22" — версия из каталога; "pegasus 42" — размер

        value = float(match.group(0).replace(",", "."))
        if MIN_SHOE_SIZE <= value <= MAX_SHOE_SIZE:
            numeric_size = _format_shoe_size(value)

    if numeric_size is not None:
        return numeric_size

    for token in query.split():
        cleaned = token.strip(".,!?;:()\"'").upper()
        if cleaned in LETTER_SIZE_CANONICAL:
            return LETTER_SIZE_CANONICAL[cleaned]

    return None

def extract_category_from_query(message: str) -> str | None:
    message = message.lower()

    for word in message.split():
        if word in CATEGORY_KEYWORDS:
            return CATEGORY_KEYWORDS[word]

    return None

# Грузинские названия цветов → канон базы (тот же, что в COLOR_KEYWORDS скрапера).
# Проверить формулировки носителем языка.
GEORGIAN_COLOR_KEYWORDS = {
    "შავი": "black",
    "თეთრი": "white",
    "წითელი": "red",
    "მუქი ლურჯი": "navy",
    "ლურჯი": "blue",
    "ცისფერი": "blue",
    "ნაცრისფერი": "gray",
    "რუხი": "gray",
    "მწვანე": "green",
    "ვარდისფერი": "pink",
    "ზეთისხილისფერი": "olive",
    "ვერცხლისფერი": "silver",
    "ოქროსფერი": "gold",
    "ყავისფერი": "coffee",
    "ნარინჯისფერი": "orange",
    "იისფერი": "purple",
    "პიტნისფერი": "mint",
    "ფერადი": "multicolor",
}

# Один словарь для поиска: английские цвета берутся из скрапера (COLOR_KEYWORDS),
# чтобы поиск и данные не расходились. Длинные ключи проверяются первыми
# ("მუქი ლურჯი" раньше "ლურჯი").
QUERY_COLOR_KEYWORDS = sorted(
    {**COLOR_KEYWORDS, **GEORGIAN_COLOR_KEYWORDS}.items(),
    key=lambda item: len(item[0]),
    reverse=True,
)


def extract_color_from_query(query: str) -> str | None:
    normalized_query = query.lower()

    for keyword, color in QUERY_COLOR_KEYWORDS:
        if keyword in normalized_query:
            return color

    return None