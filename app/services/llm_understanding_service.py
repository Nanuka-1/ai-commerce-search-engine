"""
U2 (12.10): ИИ «понимает» сообщение, которое правила НЕ поняли. Только понимание — товары выбирает НАШ поиск.

  сообщение → правила (приветствие, спасибо, артикул, доставка…) поняли? → как раньше, без ИИ
                    │ не поняли
                    ▼
           understand(message) → {intent, query, gender, size, brand, max_price, discount_only, gift,
                                  store_topic, refers_to_previous, reply}
                    │
     product_search → НАШ поиск по query (translit уже переведён на грузинский)
     store_question → НАШ ответ из store_info.json
     small_talk     → reply от ИИ (свободно, но с барьерами: без товаров, цен, наличия, ссылок)
     product_question / unclear → вежливо уточнить

Шаг U2.1 — только этот модуль + живой замер check_llm_understanding.py. В чат ещё НЕ подключён.
Любая проблема (ИИ выключен, лимит, битый JSON, неизвестное намерение) → result=None → чат работает как раньше.
"""

import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from app.services import cache_service, llm_client
from app.services.llm_text_service import EMOJI_PATTERN, STOCK_PROMISE, URL_PATTERN, _sentences
from app.services.conversation_state_service import rules_understand_nothing


INTENTS = {"product_search", "product_question", "store_question", "small_talk", "unclear"}
STORE_TOPICS = {"delivery", "returns", "payment", "stores", "contact"}
GENDERS = {"men", "women", "kids"}
LANGUAGES = {"ka", "en"}

MAX_REPLY_LENGTH = 200
MAX_REPLY_SENTENCES = 3     # 12.10: «გამარჯობა! კარგად ვარ. რით დაგეხმაროთ?» — 3 коротких, нормально
MAX_REPLY_EMOJI = 2

UNDERSTANDING_INSTRUCTION = """You read messages sent to the chat assistant of TopSport, a sports store in Georgia
(shoes, clothing, sports equipment; the catalog is in Georgian). Customers write in Georgian, English,
or Georgian in Latin letters (translit: "rogor xar" = "როგორ ხარ", "fexsacmeli" = "ფეხსაცმელი", "zoma" = "ზომა").

Your job is ONLY to understand the message. You never choose products, prices or stock.

Return ONLY a JSON object, no other text:
{
  "intent": "product_search" | "product_question" | "store_question" | "small_talk" | "unclear",
  "language": "ka" | "en",
  "search": {
    "query": string or null,
    "gender": "men" | "women" | "kids" | null,
    "size": string or null,
    "brand": string or null,
    "max_price": number or null,
    "discount_only": true | false,
    "prefer_discount": true | false,
    "new_only": true | false,
    "gift": true | false
  },
  "store_topic": "delivery" | "returns" | "payment" | "stores" | "contact" | null,
  "refers_to_previous": true | false,
  "wants_other": true | false,
  "reply": string or null
}

Intents:
- product_search: the customer wants to find products. "query" = a short search phrase IN GEORGIAN as products
  are named in a Georgian sports store: gender word + product type + model/brand + size, e.g.
  "ბავშვის ფეხსაცმელი 33", "ქალის სარბენი ფეხსაცმელი 38", "nike air max 42". Keep brand and model names in Latin.
  Use ONLY words that mean what the customer asked — never add other product types. Typical catalog words:
  ფეხსაცმელი, სარბენი ფეხსაცმელი, ბოტასი, ჩექმა, სანდალი, ჩუსტი, ქურთუკი, ჯემპრი, მაისური, შორტი, შარვალი,
  ლეგინსი, ქუდი, ჩანთა, ბურთი. A request for advice becomes a search phrase from these words:
  "what do you recommend for running in winter?" → "ზამთრის სარბენი ფეხსაცმელი".
  gender: men's (მამაკაცის) → men; women's (ქალის) → women; for a boy, girl, child, kid
  (ბიჭის, გოგოს, ბავშვის, bichistvis, gogostvis) → kids. Put the gender word into the query too.
  Budget ("up to 100 GEL", "100 ლარამდე") → max_price. A RELATIVE change of the budget is computed from the
  previous budget in RECENT CUSTOMER MESSAGES: "add 10 lari" / "10 ლარით გავზარდოთ" after "100 ლარის ფარგლებში"
  → max_price 110; "20 lari cheaper" after 100 → 80. max_price is always the final number. "ONLY on sale / with discount / ფასდაკლებით" → discount_only.
  "Discounted FIRST, if there are any" ("პირველ რიგში თუ არის ფასდაკლება", "first show the ones on sale")
  → prefer_discount=true and discount_only=false (the customer still wants to see the others).
    "New collection / new arrivals / ახალი კოლექცია / ახალი / სიახლე" → new_only=true (only the store's new products).
  gift=true ONLY if the customer explicitly says present/gift (საჩუქარი, gift, present); "for my son",
  "for a boy" (ბიჭისთვის) is NOT a gift. For a gift the query may be null if the product type is unknown.
- product_question: a question about a specific product that the message does not identify
  ("how much is this?", "ეს რა ღირს?", "this last model", "in which store is it available?").
  If it points to something shown earlier → refers_to_previous=true.
- store_question: delivery, returns/exchange, payment, store addresses/hours, contacts → store_topic.
- small_talk: greetings, thanks, "how are you", "are you a robot", "what can you do", jokes.
  Only here write "reply": 1-3 short polite sentences in the customer's language (Georgian: formal თქვენ),
  you may offer help with choosing sports goods. In reply: no products, no prices, no numbers, no links,
  never say an item is available or in stock. At most 2 emoji.
- unclear: meaningless text or you are not sure. Do not guess.

wants_other=true when the customer asks for OTHER options than those already shown
("other models", "besides these", "something else", "სხვა მოდელები", "ამის გარდა", "კიდევ რა გაქვთ").
Keep the same conditions (type, size, budget) in the search fields.

Conversation: the CUSTOMER MESSAGE may continue or correct the RECENT CUSTOMER MESSAGES
("not women's — I want for a boy", "cheaper", "other brands", "and in size 38?"). Then return the COMBINED
request: keep the earlier product type, size, budget (max_price), discount and new_only unless the customer changed them.

"language": the language of the customer (Georgian also when written in Latin letters).
Never invent sizes, brands or prices that are not in the message."""


PRODUCT_URL = re.compile(r"topsport\.ge/\S*product/", re.IGNORECASE)
# U2.3: бюджет / скидка правила не понимают → даже при бренде/поле зовём ИИ («ბავშვის … ფასდაკლებით», «nike … cheaper than 300»)
DEAL_HINT = re.compile(r"ფასდაკლ|ლარ|₾|\bgel\b|lari|\bsale\b|discount|cheap|იაფ|ბიუჯეტ|budget|\bunder \d|up to \d",
                       re.IGNORECASE)


CONVERSATION_MIN_WORDS = 4     # в разговоре фраза из 4+ слов — скорее продолжение/поправка, чем чистый запрос


def needs_understanding(message: str | None, *, brand: str | None, category: str | None,
                        is_refinement: bool, in_conversation: bool = False) -> bool:
    """U2.2: звать ИИ только если правила НЕ поняли сообщение (экономим лимит 500/день и ~1 с).
    Правила поняли: уточнение прошлого поиска («43», «შავი»), бренд, пол/категория, ссылка на товар.
    Но бюджет / скидку правила не понимают → ИИ (U2.3)."""
    text = (message or "").strip()
    if not text or is_refinement:
        return False
    if DEAL_HINT.search(text):
        return True           # бюджет / скидка — понимает только ИИ
    if in_conversation and len(text.split()) >= CONVERSATION_MIN_WORDS:
        # 12.10: «თქვენ ქალის მოდელს მაჩვენებთ და მე ბიჭის მინდა» — правила увидели «ქალის» и искали женское
        return True
    if brand or category:
        return False
    if PRODUCT_URL.search(text):
        return False          # ссылка на товар — отдельное правило (журнал п.77)
    return True


MAX_HISTORY = 4


def build_understanding_prompt(message: str, previous_query: str | None = None,
                               history: list[str] | None = None) -> tuple[str, str]:
    """(system_instruction, user_prompt). previous_query — прошлый поиск; history — прошлые сообщения клиента."""
    recent = [text for text in (history or []) if text and text.strip()][-MAX_HISTORY:]
    lines = [f"RECENT CUSTOMER MESSAGES (oldest first): {' | '.join(recent) if recent else '-'}",
             f"PREVIOUS SEARCH: {previous_query or '-'}",
             f"CUSTOMER MESSAGE: {message}"]
    return UNDERSTANDING_INSTRUCTION, "\n".join(lines)


def _text(value) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _number(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def reply_is_safe(reply: str | None) -> bool:
    """Барьеры свободного ответа: ≤ 3 коротких предложений, без обещаний наличия, ссылок, цифр (цен/размеров)."""
    if not reply:
        return False
    return (len(reply) <= MAX_REPLY_LENGTH
            and _sentences(reply) <= MAX_REPLY_SENTENCES
            and not STOCK_PROMISE.search(reply)
            and not URL_PATTERN.search(reply)
            and not re.search(r"\d", reply)
            and len(EMOJI_PATTERN.findall(reply)) <= MAX_REPLY_EMOJI)


def parse_understanding(text: str | None) -> dict | None:
    """JSON от ИИ → проверенный словарь; всё сомнительное → None или безопасное значение."""
    if not text:
        return None
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    try:
        data = json.loads(cleaned)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("intent") not in INTENTS:
        return None

    search = data.get("search") if isinstance(data.get("search"), dict) else {}
    result = {
        "intent": data["intent"],
        "language": data.get("language") if data.get("language") in LANGUAGES else None,
        "query": _text(search.get("query")),
        "gender": search.get("gender") if search.get("gender") in GENDERS else None,
        "size": _text(None if search.get("size") is None else str(search.get("size"))),
        "brand": _text(search.get("brand")),
        "max_price": _number(search.get("max_price")),
        "discount_only": search.get("discount_only") is True,
        "prefer_discount": search.get("prefer_discount") is True and search.get("discount_only") is not True,
        "new_only": search.get("new_only") is True,  # 21.10: «ახალი კოლექცია» — помнить в разговоре
        "gift": search.get("gift") is True,
        "store_topic": data.get("store_topic") if data.get("store_topic") in STORE_TOPICS else None,
        "refers_to_previous": data.get("refers_to_previous") is True,
        "wants_other": data.get("wants_other") is True,
        "reply": None,
        "reply_rejected": None,     # для отладки: ответ ИИ, не прошедший барьеры (клиенту не показывается)
    }

    if result["intent"] == "product_search" and not (result["query"] or result["gift"] or result["discount_only"]):
        result["intent"] = "unclear"          # искать нечего
    if result["intent"] == "store_question" and not result["store_topic"]:
        result["intent"] = "unclear"
    if result["intent"] == "small_talk":
        reply = _text(data.get("reply"))
        if reply_is_safe(reply):
            result["reply"] = reply
        else:
            result["reply_rejected"] = reply          # небезопасный/пустой ответ → наш шаблон
    return result


# 15.10: замер — обычно «понимание» ~1 с, но у бесплатного Gemini бывают выбросы 4–10 с.
# Не успел за лимит → result=None → чат идёт по правилам (бюджет и скидку понимает deal_rules_service).
DEFAULT_BUDGET_SECONDS = 3
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm-understanding")


def _budget_seconds() -> float:
    try:
        return float(os.getenv("LLM_UNDERSTANDING_BUDGET_SECONDS", DEFAULT_BUDGET_SECONDS))
    except ValueError:
        return DEFAULT_BUDGET_SECONDS


# 27.10 (решение пользователя: «понимает ИИ»): правила не поняли в сообщении НИЧЕГО (только незнакомые слова —
# «swimming», «ватлдвлвдыа», «rogor xar») → ждём ИИ дольше: смысл или бессмыслица — решить может только он.
# Понятные сообщения ИИ ждут как раньше. Множитель, а не отдельное число: тесты, где лимит подменён, остаются верны.
DEFAULT_PATIENT_FACTOR = 2.5      # 3 с × 2.5 = 7.5 с


def _patient_budget_seconds() -> float:
    try:
        factor = float(os.getenv("LLM_UNDERSTANDING_PATIENT_FACTOR", DEFAULT_PATIENT_FACTOR))
    except ValueError:
        factor = DEFAULT_PATIENT_FACTOR
    return _budget_seconds() * max(factor, 1.0)

# 15.10: кэш понимания. Только ПЕРВОЕ сообщение разговора (без истории и прошлого поиска):
# в разговоре смысл зависит от прошлых сообщений. Версия инструкции в ключе: поменяли инструкцию → старое не берём.
UNDERSTANDING_CACHE_TTL = 7 * 24 * 3600
PROMPT_VERSION = hashlib.sha1(UNDERSTANDING_INSTRUCTION.encode("utf-8")).hexdigest()[:8]


def understanding_cache_key(message: str, previous_query: str | None = None,
                            history: list[str] | None = None) -> str | None:
    if previous_query or any(text and text.strip() for text in (history or [])):
        return None
    normalized = " ".join((message or "").lower().split())
    return f"llm:understand:{PROMPT_VERSION}:{normalized}" if normalized else None


def understand(message: str, previous_query: str | None = None, history: list[str] | None = None) -> dict:
    """{"result": dict | None, "model", "ms", "raw", "errors"}. Никогда не бросает исключение
    и не ждёт дольше лимита (LLM_UNDERSTANDING_BUDGET_SECONDS, по умолчанию 3 с;
    27.10: если правила не поняли ничего — × LLM_UNDERSTANDING_PATIENT_FACTOR, по умолчанию 7.5 с).
    Повтор первого сообщения — из кэша (model="cache", ms=0)."""
    cache_key = understanding_cache_key(message, previous_query, history)
    if cache_key:
        cached = cache_service.get(cache_key)
        if cached:
            return {**cached, "model": "cache", "ms": 0.0}
    system, prompt = build_understanding_prompt(message, previous_query, history)
    started = time.perf_counter()
    future = _executor.submit(llm_client.generate_text, system, prompt)
    try:
        budget = _patient_budget_seconds() if rules_understand_nothing(message) else _budget_seconds()
        response = future.result(timeout=budget)
    except FutureTimeout:
        # ответ модели (если придёт позже) просто не используем — клиент не ждёт
        return {"result": None, "model": None, "ms": round((time.perf_counter() - started) * 1000, 1),
                "raw": None, "errors": ["timeout"]}
    understood = {
        "result": parse_understanding(response.get("text")),
        "model": response.get("model"),
        "ms": response.get("ms"),
        "raw": response.get("text"),
        "errors": response.get("errors", []),
    }
    if cache_key and understood["result"] is not None:      # ошибки / таймауты не кэшируем
        cache_service.set(cache_key, understood, ttl=UNDERSTANDING_CACHE_TTL)
    return understood