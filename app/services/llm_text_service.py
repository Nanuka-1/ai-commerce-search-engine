"""
LLM-слой ответа (шаг 3.7a): ЧТО даём модели и КАК проверяем её ответ. Без вызова Gemini.

Принцип: Search decides → Business rules decide → LLM speaks.
  - LLM пишет только короткое вступление (1–3 предложения) к найденным товарам.
  - Карточки товаров (цена, размеры, ссылка) показываются из наших данных, не из текста LLM.
  - Факты — только то, что нашёл поиск и сказали правила (наш шаблонный текст).
  - Ответ LLM проверяется кодом; не прошёл проверку → клиент получает шаблон.
"""
import re

MAX_ITEMS_IN_FACTS = 5
MAX_TEXT_LENGTH = 400        # символов: 1–3 предложения
MAX_EMOJI = 2
MAX_SENTENCES = 3

LANGUAGE_NAMES = {"ka": "Georgian", "en": "English"}

# Режимы, где LLM не нужен: шаблон уже точный (вопрос о размере) — экономим лимит.
SKIP_RESULT_MODES = {"need_size"}

SYSTEM_INSTRUCTION = """You are a polite sales consultant of TopSport, a sports store in Georgia.
Write a short friendly reply (1-2 sentences) to the CUSTOMER MESSAGE about the products the search has already found.

Rules:
- First answer the CUSTOMER MESSAGE directly, like a person would.
  If the customer asks "do you have X in size N?" and the BASE MESSAGE confirms the size was found,
  start with "კი, ვიპოვე ..." / "Yes, I found ...".
  If the BASE MESSAGE says something was NOT found, say that honestly first — never say "yes" then.
- CUSTOMER CONDITIONS (if given) are what the customer asked for (size, budget, discount).
  Mention a condition only if it helps the answer; never invent other conditions.
- Do not repeat the customer's words or the product names one by one.
- Write ONLY in {language}. In Georgian, address the customer formally (თქვენ).
  Product names in the facts may be in Georgian — still answer ONLY in {language}.
- Do NOT greet (no "Hello", "მოგესალმებით", "გამარჯობა"): the conversation is already going on.
- At most 3 short sentences.
- Use ONLY the facts below. Never invent products, prices, sizes, discounts, stock or deadlines.
- Keep the meaning of the BASE MESSAGE: it is what the store must say (for example, ask to check stock in a store on the website).
  If the BASE MESSAGE asks the customer to specify the model or the size, keep that request.
- Never promise that an item is in stock in a store — only the website knows that.
  Say "found" (ვიპოვე). Never say "we have", "in stock", "გვაქვს", "მარაგშია".
- Do not attribute qualities to products (warm, waterproof, light, comfortable...) unless the word is in the product names in the facts.
- Do not write links. Do not list all products or prices — the product cards are shown separately.
- You may use 1-2 emoji that fit the product type: 👟 shoes, 🧥 jackets and clothing, 🏃 running, ⚽ football, 🔥 discount, ✅ confirmation. No more than 2.
- Output only the text for the customer, nothing else."""


def _field(item, name):
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def should_use_llm(context) -> bool:
    """LLM вызываем только когда есть найденные товары и это не вопрос о размере."""
    if context is None or not getattr(context, "total_count", 0) or not getattr(context, "items", None):
        return False
    return getattr(context, "result_mode", None) not in SKIP_RESULT_MODES


def _format_price(value) -> str | None:
    if value is None:
        return None
    return f"{value:g}"


def _item_line(item) -> str:
    parts = [str(_field(item, "name") or "?")]
    brand = _field(item, "brand")
    if brand:
        parts.append(f"brand: {brand}")
    sizes = _field(item, "sizes") or ([_field(item, "size")] if _field(item, "size") else [])
    if sizes:
        parts.append("sizes: " + ", ".join(str(size) for size in sizes))
    price = _field(item, "price_from") or _field(item, "price")
    if price is not None:
        parts.append(f"price: {_format_price(price)} GEL")
        regular = _field(item, "regular_price")
        if regular and regular > price:
            discount = round((1 - price / regular) * 100)
            parts.append(f"regular price: {_format_price(regular)} GEL, discount: {discount}%")
    return "- " + "; ".join(parts)


def describe_conditions(size=None, max_price=None, discount_only=False, prefer_discount=False,
                        new_only=False) -> str | None:
    """13.10: условия, которые поняли из разговора, — чтобы ИИ ответил на сам вопрос («კი, 38 ზომაში…»).
    21.10: new_only → «new collection only»: поиск показал только новинки — ИИ может это сказать (new_claim пропустит)."""
    parts = []
    if new_only:
        parts.append("new collection only")
    if size:
        parts.append(f"size {size}")
    if max_price:
        parts.append(f"budget up to {_format_price(max_price)} GEL")
    if discount_only:
        parts.append("only discounted products")
    elif prefer_discount:
        parts.append("discounted products first")
    return "; ".join(parts) or None


def build_facts(context, base_message: str, customer_message: str, conditions: str | None = None) -> str:
    """Факты для LLM: сообщение клиента, понятые условия, наш шаблонный текст, до 5 карточек."""
    items = list(getattr(context, "items", None) or [])[:MAX_ITEMS_IN_FACTS]
    lines = [
        f"CUSTOMER MESSAGE: {customer_message}",
        *([f"CUSTOMER CONDITIONS: {conditions}"] if conditions else []),
        f"BASE MESSAGE: {base_message}",
        f"PRODUCTS FOUND: {getattr(context, 'total_count', len(items))}",
        *[_item_line(item) for item in items],
    ]
    return "\n".join(lines)


def build_prompt(context, base_message: str, customer_message: str, language: str,
                 conditions: str | None = None) -> tuple[str, str]:
    """(system_instruction, user_prompt)"""
    system = SYSTEM_INSTRUCTION.format(language=LANGUAGE_NAMES.get(language, "Georgian"))
    return system, build_facts(context, base_message, customer_message, conditions)


# --- проверка ответа LLM ---

# Обещание наличия — неправда: наличие по филиалам знает только сайт (решение пользователя 07.10, 3.7d 09.10).
STOCK_PROMISE = re.compile(r"გვაქვს|მარაგშია|\bwe have\b|\bin stock\b", re.IGNORECASE)
# 20.10: «ახალი კოლექციიდან ვიპოვე…» при товарах со скидкой — неправда. Признак новинки появится в этапе 3 (is_new);
# пока факты не говорят «NEW COLLECTION», ИИ не может называть товары новыми.
NEW_CLAIM = re.compile(
    r"ახალ\w*\s+(?:კოლექც|მოდელ|სეზონ)|სიახლ|\bnew\s+(?:collection|arrivals?|season|models?)\b"
    r"|\blatest\s+(?:collection|models?)\b",
    re.IGNORECASE,
)
URL_PATTERN = re.compile(r"https?://|www\.|\.ge\b|\.com\b", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?")
EMOJI_PATTERN = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⬆↔-↪]")
GEORGIAN = re.compile("[Ⴀ-ჿ]")
LATIN = re.compile("[A-Za-z]")


# Приветствие в начале ответа убираем кодом (разговор уже идёт) — дешевле, чем отклонять весь ответ.
GREETING_PREFIX = re.compile(
    r"^\s*(მოგესალმებით|გამარჯობა|hello|hi|welcome to topsport)\s*[!,.]?\s*", re.IGNORECASE)


def clean_llm_text(text: str | None) -> str:
    text = (text or "").strip()
    while True:
        cleaned = GREETING_PREFIX.sub("", text, count=1).strip()
        if cleaned == text:
            return text
        text = cleaned


def _sentences(text: str) -> int:
    # части между . ! ? в которых есть буквы (эмодзи и пробелы не считаются)
    return len([part for part in re.split(r"[.!?]+", text) if re.search(r"\w", part)])


def _numbers(text: str) -> set[str]:
    result = set()
    for number in NUMBER_PATTERN.findall(text):
        value = float(number.replace(",", "."))
        result.add(f"{value:g}")
    return result


def validate_llm_text(text: str | None, facts: str, language: str) -> tuple[bool, str]:
    """(ok, причина). Любая ошибка → используем шаблон."""
    if not text or not text.strip():
        return False, "empty"
    text = text.strip()
    if len(text) > MAX_TEXT_LENGTH:
        return False, "too_long"
    if _sentences(text) > MAX_SENTENCES:
        return False, "too_many_sentences"
    if STOCK_PROMISE.search(text):
        return False, "stock_promise"
    if NEW_CLAIM.search(text) and "new collection" not in facts.lower():
        return False, "new_claim"
    if URL_PATTERN.search(text):
        return False, "link"
    if len(EMOJI_PATTERN.findall(text)) > MAX_EMOJI:
        return False, "too_many_emoji"
    unknown = _numbers(text) - _numbers(facts)
    if unknown:
        return False, f"unknown_numbers:{','.join(sorted(unknown))}"   # выдуманная цена/размер/процент
    georgian = len(GEORGIAN.findall(text))
    latin = len(LATIN.findall(text))
    if language == "ka" and georgian <= latin:
        return False, "wrong_language"      # бренды латиницей допустимы, но текст должен быть грузинским
    if language == "en" and georgian >= latin:
        # названия товаров в каталоге грузинские ("Nike მამაკაცის ქურთუკი") — цитата допустима,
        # но сам текст должен быть английским (зеркально правилу для ka)
        return False, "wrong_language"
    return True, "ok"