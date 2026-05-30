import re


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
}

CATEGORY_KEYWORDS = {
    "men": "men",
    "male": "men",
    "man": "men",
    "მამაკაცი": "men",
    "მამაკაცის": "men",

    "women": "women",
    "woman": "women",
    "female": "women",
    "ქალი": "women",
    "ქალის": "women",

    "kids": "kids",
    "kid": "kids",
    "child": "kids",
    "children": "kids",
    "ბავშვი": "kids",
    "ბავშვის": "kids",
}

CATEGORY_DB_SLUGS = {
    "men": "mamakatsis",
    "women": "qalis-fekhsatsmeli",
    "kids": "bavshvis-fekhsatsmeli",
}


SKU_PATTERN = re.compile(r"^(?=.*\d)[A-Z0-9]+(?:-[A-Z0-9._]+)*$", re.IGNORECASE)

def map_category_to_db_slug(category: str | None) -> str | None:
    if category is None:
        return None

    return CATEGORY_DB_SLUGS.get(category)

def normalize_text(message: str) -> str:
    return re.sub(r"\s+", " ", message.strip().lower())


def is_greeting(message: str) -> bool:
    normalized = normalize_text(message)

    if normalized in GREETING_WORDS:
        return True

    return any(normalized.startswith(word + " ") for word in GREETING_WORDS)


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


def is_sku(message: str) -> bool:
    normalized = message.strip()
    if not normalized:
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

def extract_size_from_query(query: str):
    match = re.search(r"\b\d+(?:\.\d+)?\b", query)

    if match:
        size = match.group(0)

        try:
            size_int = int(float(size))

            # Allowable shoe size
            if 20 <= size_int <= 55:
                return str(size_int)

        except ValueError:
            pass

    return None

def extract_category_from_query(message: str) -> str | None:
    message = message.lower()

    for word in message.split():
        if word in CATEGORY_KEYWORDS:
            return CATEGORY_KEYWORDS[word]

    return None

def extract_color_from_query(query: str) -> str | None:
    normalized_query = query.lower()

    color_keywords = {
        "white": "white",
        "black": "black",
        "red": "red",
        "blue": "blue",
        "green": "green",
        "grey": "grey",
        "gray": "grey",
        "თეთრი": "white",
        "შავი": "black",
        "წითელი": "red",
        "ლურჯი": "blue",
    }

    for keyword, color in color_keywords.items():
        if keyword in normalized_query:
            return color

    return None