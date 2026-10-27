"""
22.10 (этап 3, п.4): карточка условий разговора — dialog state tracking.
Дизайн и решения пользователя: claude/dialog-state-design.md, журнал part2 п.131.

ИИ (или правила) понимают ОДНО сообщение → StatePatch («что сказано сейчас»).
Эта программа ведёт разговор: merge(карточка, patch) → новая карточка + решение.
  - названное в сообщении заменяет своё поле, остальное остаётся;
  - сменился пол / тип товара (обувь ↔ одежда), а размер не назван → СПРОСИТЬ размер (без карточек);
  - сменилась модель, а бюджет был → СПРОСИТЬ «тот же бюджет?»;
  - не понятно, ЧТО искать (только бюджет / только пол) → спросить тип товара;
  - «ახალი ძებნა / თავიდან / new search» → с чистого листа.
Чистые функции: без базы, без ИИ, без кэша.

Текст для поиска = бренд + модель + слово пола + вид + товар (как сказал клиент) + размер.
Слова вроде «მაინტერესებს / გაქვთ» в товар не попадают — они не меняют, ЧТО ищем.
"""
import re
from dataclasses import dataclass, field, fields, replace

from app.services.deal_rules_service import parse_deal_filters
from app.services.intent_router import extract_category_from_query, extract_size_from_query
from app.services.query_parser_service import extract_brand_from_query, extract_model_hint_from_query

# Тип товара: корень слова → (как пишет каталог, семейство). Семейство решает, совместим ли размер:
# обувной 36 не подходит куртке → при смене семейства спрашиваем размер.
PRODUCTS = {
    "ფეხსაცმ": ("ფეხსაცმელი", "footwear"), "ბოტას": ("ბოტასი", "footwear"), "კედ": ("კედები", "footwear"),
    "სანდალ": ("სანდალი", "footwear"), "ჩუსტ": ("ჩუსტი", "footwear"), "ჩექმ": ("ჩექმა", "footwear"),
    "shoe": ("ფეხსაცმელი", "footwear"), "sneaker": ("ბოტასი", "footwear"), "boot": ("ჩექმა", "footwear"),
    "ტანსაცმ": ("ტანსაცმელი", "clothing"), "ქურთუკ": ("ქურთუკი", "clothing"), "ჯემპრ": ("ჯემპრი", "clothing"),
    "მაისურ": ("მაისური", "clothing"), "შორტ": ("შორტი", "clothing"), "შარვალ": ("შარვალი", "clothing"),
    "ლეგინს": ("ლეგინსი", "clothing"), "ჟაკეტ": ("ჟაკეტი", "clothing"), "ჰუდ": ("ჰუდი", "clothing"),
    "კოსტიუმ": ("კოსტიუმი", "clothing"), "ჟილეტ": ("ჟილეტი", "clothing"),
    "jacket": ("ქურთუკი", "clothing"), "hoodie": ("ჰუდი", "clothing"), "shirt": ("მაისური", "clothing"),
    "short": ("შორტი", "clothing"), "pant": ("შარვალი", "clothing"),
    "ზურგჩანთ": ("ზურგჩანთა", "accessory"), "ჩანთ": ("ჩანთა", "accessory"), "ქუდ": ("ქუდი", "accessory"),
    "ბურთ": ("ბურთი", "accessory"), "bag": ("ჩანთა", "accessory"), "backpack": ("ზურგჩანთა", "accessory"),
    "cap": ("ქუდი", "accessory"), "ball": ("ბურთი", "accessory"),
}
# Уточнение вида того же товара («არა, სპორტული მინდა») — размер не трогает
STYLES = {"სპორტულ": "სპორტული", "სარბენ": "სარბენი", "ზამთრ": "ზამთრის",
          "running": "სარბენი", "sport": "სპორტული", "winter": "ზამთრის"}

RESET = re.compile(r"ახალი\s+ძებნ[ა-ჰ]*|თავიდან|სხვა\s+რამე\s+მინდა|\bnew\s+search\b|\bstart\s+over\b", re.IGNORECASE)
YES_WORDS = {"კი", "დიახ", "ki", "diax", "yes", "ok", "okay", "იგივე", "igive", "same"}
NO_WORDS = {"არა", "ara", "no"}
# Слова, которые не меняют, ЧТО ищем (21.10: «მაინტერესებს» превращал продолжение в новый поиск)
FILLER_WORDS = {
    "მინდა", "მაინტერესებს", "მჭირდება", "მაქვს", "გაქვთ", "გაქ", "თუ", "და", "ან", "ხომ", "რამე", "არის",
    "ზომა", "ზომის", "ზომაში", "ზომით", "მაჩვენე", "მაჩვენეთ", "მიჩვენე", "მიჩვენეთ", "გთხოვთ", "მოდელი",
    "მოდელები", "ვარიანტი", "ვარიანტები", "კიდევ", "კიდე", "სხვა", "ასევე", "ოღონდ",
    "ეს", "ეგ", "ამის", "ამ", "იმ", "ესეც", "ეგეც",          # 26.10: «ეს თუ გაქვთ» — «это», не товар
    "i", "want", "need", "have", "do", "you", "please", "show", "me", "size", "for", "the", "a", "in", "and",
} | YES_WORDS | NO_WORDS
GENDER_WORDS = {"men": "მამაკაცის", "women": "ქალის", "kids": "ბავშვის"}
# 26.10 (замер): в каталоге детское НЕ делится на девочек / мальчиков (1 521 модель, пометки у ~20 Puma).
# «для девочки / мальчика» → ищем детское (как пишет каталог: «ბავშვის») и честно говорим об этом.
CHILD = re.compile(r"(?<![ა-ჰ])(?:გოგო|გოგონ|ბიჭ)[ა-ჰ]*|\b(?:girls?|boys?)\b", re.IGNORECASE)

SEARCH, ASK, CLARIFY, RESET_DONE = "search", "ask", "clarify", "reset"
UNCLEAR = "unclear"     # 26.10: в сообщении ничего понятного («დჯვდკლვჯ», «аичичи») — переспросить, карточку не трогать


@dataclass
class SearchState:
    """Карточка условий разговора (кэш chat:state:{user}, 30 мин)."""
    gender: str | None = None
    gender_word: str | None = None      # как назвал клиент («women», «ქალის») — для текста поиска
    product: str | None = None          # «ფეხსაცმელი» — тип товара (семейство для размера)
    product_text: str | None = None     # «საცურაო ქუდი», «ზამთრის სარბენი ფეხსაცმელი» — как сказал клиент
    style: str | None = None            # «სარბენი», «სპორტული»
    model: str | None = None            # «samba»
    brand: str | None = None
    size: str | None = None
    max_price: float | None = None
    discount_only: bool = False
    prefer_discount: bool = False
    new_only: bool = False
    exclude_brands: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)   # что спросили и ждём ответа: "size", "budget"


@dataclass
class StatePatch:
    """Что сказано в ЭТОМ сообщении. None / False = «не сказано» (не значит «убрать»)."""
    gender: str | None = None
    gender_word: str | None = None
    product: str | None = None
    product_text: str | None = None
    loose_text: str | None = None       # незнакомые слова без типа товара — товар только в 1-м сообщении
    style: str | None = None
    model: str | None = None
    brand: str | None = None
    size: str | None = None
    max_price: float | None = None
    discount_only: bool = False
    prefer_discount: bool = False
    new_only: bool = False
    reset: bool = False
    yes: bool = False
    no: bool = False
    child: bool = False                 # клиент сказал «девочка / мальчик» — в каталоге этого деления нет


@dataclass
class Decision:
    action: str                          # search | ask | clarify | reset
    ask: list[str] = field(default_factory=list)       # "size", "budget", "product"


def _family(product: str | None) -> str | None:
    for _root, (canonical, family) in PRODUCTS.items():
        if canonical == product:
            return family
    return None


def _find(words: list[str], table: dict) -> str | None:
    for word in words:
        for root, value in table.items():
            if word.startswith(root):
                return value[0] if isinstance(value, tuple) else value
    return None


def _product_words(words: list[str], brand: str | None, model: str | None) -> list[str]:
    """Слова о товаре: без пола, размера, бренда, модели и связок."""
    skip = set((model or "").split()) | ({brand} if brand else set())
    return [word for word in words
            if word not in FILLER_WORDS and word not in skip
            and not extract_category_from_query(word) and not CHILD.match(word)
            and not extract_size_from_query(word)
            and not extract_brand_from_query(word)]


def _gender_word(words: list[str]) -> str | None:
    return next((word for word in words if extract_category_from_query(word)), None)


def patch_from_rules(message: str | None) -> StatePatch:
    """Правила: то же, что поиск уже умеет (пол, размер, бренд, модель, бюджет / скидка / новинки) + тип товара."""
    text = (message or "").strip()
    if RESET.search(text):
        # «ახალი ძებნა: ქალის ქურთუკი M» — сброс, а остаток разбираем как первое сообщение
        return replace(patch_from_rules(RESET.sub(" ", text)), reset=True)
    deal = parse_deal_filters(text)
    cleaned = deal.cleaned.lower()
    words = re.findall(r"\w+", cleaned)
    brand = extract_brand_from_query(cleaned)
    model = extract_model_hint_from_query(cleaned)
    product = _find(words, PRODUCTS)
    rest = " ".join(_product_words(words, brand, model)) or None
    child = bool(CHILD.search(cleaned))
    return StatePatch(
        gender="kids" if child else extract_category_from_query(cleaned),
        gender_word=GENDER_WORDS["kids"] if child else _gender_word(words), child=child,
        product=product, product_text=rest if product else None, loose_text=None if product else rest,
        style=_find(words, STYLES), model=model, brand=brand, size=extract_size_from_query(cleaned),
        max_price=deal.max_price, discount_only=deal.discount_only, prefer_discount=deal.prefer_discount,
        new_only=deal.new_only,
        yes=any(word in YES_WORDS for word in words), no=any(word in NO_WORDS for word in words),
    )


def patch_from_ai(result: dict, message: str | None = None) -> StatePatch:
    """Поля ответа ИИ (llm_understanding_service.parse_understanding) → patch. Товар — из query ИИ (ИИ пишет
    короткую фразу о товаре, ей доверяем). Сброс / да / нет / новинки — правилами по исходному сообщению."""
    query = (result.get("query") or "").lower()
    words = re.findall(r"\w+", query)
    brand = (result.get("brand") or "").lower() or extract_brand_from_query(query) if query else None
    model = extract_model_hint_from_query(query) if query else None
    by_rules = patch_from_rules(message) if message else StatePatch()
    # 22.10: ИИ написал пол в query («ბავშვის ფეხსაცმელი»), а поле gender оставил пустым → берём из query
    gender = result.get("gender") or extract_category_from_query(query)
    word = _gender_word(words)
    gender_word = word if word and extract_category_from_query(word) == gender else GENDER_WORDS.get(gender)
    if by_rules.child or CHILD.search(query):
        gender, gender_word = "kids", GENDER_WORDS["kids"]   # 26.10: девочки / мальчики = детское каталога
    return StatePatch(
        gender=gender, gender_word=gender_word,
        product=_find(words, PRODUCTS),
        product_text=" ".join(_product_words(words, brand, model)) or None,
        style=_find(words, STYLES), model=model, brand=brand or None, size=result.get("size"),
        max_price=result.get("max_price"),
        discount_only=bool(result.get("discount_only")), prefer_discount=bool(result.get("prefer_discount")),
        new_only=bool(result.get("new_only")) or by_rules.new_only,
        reset=by_rules.reset, yes=by_rules.yes, no=by_rules.no,
        child=by_rules.child or bool(CHILD.search(query)),
    )


def _says_nothing(patch: StatePatch) -> bool:
    """Ни одного понятного поля: ни пола, ни товара, ни размера, ни бюджета, ни «да / нет / сначала»."""
    return not any(getattr(patch, item.name) for item in fields(StatePatch) if item.name != "loose_text")


def rules_understand_nothing(message: str | None) -> bool:
    """27.10: правила не поняли в сообщении НИЧЕГО — только незнакомые слова («ватлдвлвдыа», «swimming», «rogor xar»).
    Тогда ждём ИИ дольше (llm_understanding_service): решить «смысл или бессмыслица» может только он."""
    patch = patch_from_rules(message)
    return bool(patch.loose_text) and _says_nothing(patch) and not patch.reset


def has_anchor(state: SearchState | None) -> bool:
    """В карточке есть то, что мы ПОНЯЛИ: тип товара, бренд или модель. Незнакомые слова («swimming»,
    «ватлдвлвдыа») якорем не считаются: их подтверждает только поиск по словам (chat_use_case)."""
    return bool(state and (state.product or state.brand or state.model))


def merge(state: SearchState | None, patch: StatePatch) -> tuple[SearchState, Decision]:
    """Карточка + сообщение → новая карточка + что делать. Решения пользователя 21.10."""
    if has_anchor(state) and patch.loose_text and _says_nothing(patch):
        # 26.10 (живьём): бессмыслица посреди разговора считалась «повтором» → те же карточки снова.
        # Незнакомые слова без понятного — не меняют поиск: переспрашиваем, карточка как была.
        return state, Decision(UNCLEAR)
    old = SearchState() if (state is None or patch.reset) else state
    new = replace(old, exclude_brands=list(old.exclude_brands), pending=[])

    # ответ на прошлый вопрос о бюджете: «კი / იგივე» — оставить, «არა» — убрать, число — заменить (ниже)
    if "budget" in old.pending and patch.max_price is None and patch.no:
        new.max_price = None

    gender_changed = bool(patch.gender and old.gender and patch.gender != old.gender)
    family_changed = bool(patch.product and old.product and _family(patch.product) != _family(old.product))
    model_changed = bool(patch.model and patch.model != old.model)

    for name in ("gender", "gender_word", "product", "product_text", "style", "model", "brand", "size",
                 "max_price"):
        value = getattr(patch, name)
        if value is not None:
            setattr(new, name, value)
    for flag in ("discount_only", "prefer_discount", "new_only"):
        if getattr(patch, flag):
            setattr(new, flag, True)
    if patch.discount_only:
        new.prefer_discount = False
    if patch.loose_text and not patch.product_text and not has_anchor(new):
        # незнакомые слова без понятого товара («swimming») — ищем как есть; следующее такое сообщение
        # ЗАМЕНЯЕТ их (26.10: «ватлдвлвдыа» оставался «товаром» и мешал «swimming»)
        new.product_text = patch.loose_text
    if patch.style and not patch.product and new.product:
        new.product_text = new.product          # «არა, სპორტული» — вид меняет описание того же товара
    if family_changed and patch.style is None:
        new.style = None                        # «სარბენი» от обуви не переносим на куртку
    if gender_changed or family_changed or model_changed:
        new.exclude_brands = []                 # «другой бренд» относился к прошлому товару

    if (gender_changed or family_changed) and patch.size is None:
        new.size = None
        new.pending.append("size")
    elif "size" in old.pending and not new.size:
        new.pending.append("size")              # спросили размер, а ответа нет — спрашиваем снова
    if model_changed and old.max_price and patch.max_price is None and not (patch.yes or patch.no):
        new.pending.append("budget")

    if patch.reset and not any((new.gender, new.product_text, new.model, new.brand, new.size)):
        return new, Decision(RESET_DONE)
    if new.pending:
        return new, Decision(ASK, list(new.pending))
    if not (new.product_text or new.product or new.model or new.brand):
        return new, Decision(CLARIFY, ["product"])
    return new, Decision(SEARCH)


def search_text(state: SearchState) -> str:
    """Текст для поиска из карточки: «nike women 40», «ქალის სპორტული ფეხსაცმელი 36»."""
    product = state.product_text or state.product
    style = state.style if state.style and state.style not in (product or "") else None
    parts = [(state.brand or "").lower(), state.model, state.gender_word or GENDER_WORDS.get(state.gender), style, product,
             state.size]
    return " ".join(part for part in parts if part)


def search_filters(state: SearchState) -> dict:
    """Фильтры для _handle_product_search (бюджет, скидка, новинки, исключённые бренды)."""
    return {"max_price": state.max_price, "discount_only": state.discount_only,
            "prefer_discount": state.prefer_discount, "new_only": state.new_only,
            "exclude_brands": list(state.exclude_brands) or None}


def describe_state(state: SearchState) -> str:
    """Строка понятых условий над карточками: «ქალის · ფეხსაცმელი · 36 · ≤ 300 ₾ · ახალი კოლექცია»."""
    parts = [GENDER_WORDS.get(state.gender), state.brand, state.model, state.product_text or state.product,
             state.size, f"≤ {state.max_price:g} ₾" if state.max_price else None,
             "ფასდაკლებით" if state.discount_only else None, "ახალი კოლექცია" if state.new_only else None]
    return " · ".join(part for part in parts if part)


def state_to_dict(state: SearchState) -> dict:
    return {item.name: getattr(state, item.name) for item in fields(SearchState)}


def state_from_dict(data: dict | None) -> SearchState | None:
    if not data:
        return None
    known = {item.name for item in fields(SearchState)}
    return SearchState(**{key: value for key, value in data.items() if key in known})