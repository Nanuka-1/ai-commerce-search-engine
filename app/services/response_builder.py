import re
from urllib.parse import quote_plus

from app.schemas.search_context import SearchContext
from app.services.translations import translate, resolve_language


AVAILABILITY_CTA = {
    "en": " Check availability and order on our website without leaving home — popular sizes sell out fast!",
    "ka": " შეამოწმეთ მარაგი და შეუკვეთეთ ჩვენს საიტზე სახლიდან გაუსვლელად — პოპულარული ზომები სწრაფად იყიდება!",
}

DEFAULT_RESPONSE_ITEMS_LIMIT = 5

# Поиск сайта (адрес со страницы результатов, 07.10): /ka/ или /en/ — язык клиента.
SITE_SEARCH_URL = "https://topsport.ge/{language}/products?term={term}&search_type=name"

# Ответы, где "есть в вашем размере" было бы неправдой или не к месту.
# 13.10: «уточните модель — SKU, название, фото…» говорим один раз за разговор; дальше — «აი 5 ვარიანტი 👇»
SHORT_AFTER_FIRST_KEYS = {"search_need_model_many", "search_broad_query", "search_found_many"}

NO_SIZE_NOTE_KEYS = {"search_need_size", "search_size_alternatives",
                     "search_brand_fallback", "search_similar_model"}


def build_site_search_url(query: str | None, size: str | None, language: str,
                          item_names: list[str] | None = None) -> str:
    """Ссылка на поиск сайта по запросу клиента. Размер из запроса убираем:
    сайт ищет по названию ("adidas samba 46" → "adidas samba"), размер клиент выберет на сайте.
    13.10: поиск сайта требует ВСЕ слова в названии → «ბავშვის ბიჭის ფეხსაცმელი» давал 0 (в названиях нет «ბიჭის»).
    Если есть найденные товары — оставляем только слова, которые есть в их названиях."""
    term = query or ""
    if size:
        term = re.sub(rf"(?<!\S){re.escape(size)}(?!\S)", " ", term, flags=re.IGNORECASE)
    term = " ".join(term.split()) or (query or "").strip()
    names = " ".join(name for name in (item_names or []) if name).lower()
    if names:
        words = [word for word in term.split() if word.strip(".,!?;:()").lower() in names]
        if words:
            term = " ".join(words)
    return SITE_SEARCH_URL.format(language=language, term=quote_plus(term))


GEORGIAN_VOWEL_ENDINGS = "aeiou"


def georgian_genitive(model: str | None) -> str:
    """Родительный падеж названия модели по-грузински: на гласную → «-ს», на согласную → «-ის».
    13.10 (замечание пользователя): «„samba“-ის» звучит неправильно → «Samba-ს», «Pegasus-ის»."""
    name = (model or "").strip()
    if not name:
        return ""
    shown = name.upper() if len(name) <= 3 else name.title()        # nmd → NMD, samba → Samba
    return f"{shown}-ს" if name[-1].lower() in GEORGIAN_VOWEL_ENDINGS else f"{shown}-ის"


def _main_message_key(context: SearchContext) -> str:
    # Одна цепочка: первое подходящее правило решает текст.
    # Специфичные режимы (размер, модель, альтернативы) важнее общих.
    if context.result_mode == "need_size":
        return "search_need_size"
    if context.result_mode == "need_model":
        return "search_need_model_one" if context.total_count == 1 else "search_need_model_many"
    if context.matched_by == "size_alternatives":
        return "search_size_alternatives"
    if context.matched_by == "brand_fallback":
        return "search_brand_fallback"
    if context.result_mode == "exact_model_match":
        return "search_exact_model"
    if context.result_mode == "fallback_similar":
        return "search_similar_model"
    if context.result_mode == "broad_query":
        return "search_broad_query"
    if context.total_count == 1:
        return "search_found_one"
    return "search_found_many"


def _color_note_key(context: SearchContext, items: list) -> str | None:
    # Цвет дополняет основной ответ, а не заменяет его.
    if not context.detected_color:
        return None
    item_colors = [
        item.get("color") if isinstance(item, dict) else getattr(item, "color", None)
        for item in items
    ]
    if context.detected_color in item_colors:
        return "search_color_matched"
    return "search_color_unknown"


def build_response(context: SearchContext, user_id: str, response_type: str,
                   locale: str | None = None, stock_hint: bool = True):
    """stock_hint (13.10): подсказку «наличие в филиале — на странице товара» и призыв заказать на сайте
    говорим ОДИН раз в разговоре (решает chat_use_case). Повтор в каждом ответе звучит как робот."""
    items = context.items[:DEFAULT_RESPONSE_ITEMS_LIMIT]

    serialized_items = [
        item if isinstance(item, dict) else {
            "id": item.id,
            "sku": item.sku,
            "name": item.name,
            "price": item.price,
            "product_url": item.product_url,
            "available": item.is_active,
        }
        for item in items
    ]

    shown = len(serialized_items)
    has_more = context.total_count > (context.offset + shown)
    next_offset = context.offset + shown if has_more else None

    response = {
        "type": response_type,
        "data": {
            "user_id": user_id,
            "results": {
                "query": context.query,
                "matched_by": context.matched_by,
                "search_strategy": context.search_strategy,
                "items": serialized_items,
                "total": context.total_count,
                "shown": shown,
                "has_more": has_more,
                "next_offset": next_offset,
            },
        },
    }

    language = resolve_language(context.query, locale)
    item_names = [item.get("name") for item in serialized_items if isinstance(item, dict)]
    site_search_url = build_site_search_url(context.query, context.detected_size, language, item_names)
    response["data"]["results"]["site_search_url"] = site_search_url   # для кнопки "Смотреть на сайте"
    params = {
        "query": context.query,
        "model": context.model_hint,
        "model_gen": georgian_genitive(context.model_hint),
        "size": context.detected_size,
        "color": context.detected_color,
        "total": context.total_count,
        "shown": shown,
        "url": site_search_url,
    }

    if context.total_count == 0:
        # 13.10: ссылку на поиск сайта в текст НЕ ставим — сайт ищет фразу целиком и часто показывает 0 товаров
        # (тупик для клиента). Вместо неё — что поменять: размер, модель, бюджет.
        key = "search_size_not_found_short" if context.detected_size else "search_no_products"
        response["message"] = translate(key, language).format(**params)
        return response

    main_key = _main_message_key(context)
    if not stock_hint and main_key in SHORT_AFTER_FIRST_KEYS:
        main_key = "search_more_short"
    message = translate(main_key, language).format(**params)
    if context.detected_size and main_key not in NO_SIZE_NOTE_KEYS:
        # первый раз: "нашли размер" + где проверить наличие в филиале; дальше — коротко "размер есть ✅"
        size_key = "search_size_available" if stock_hint else "search_size_found_short"
        message = translate(size_key, language).format(**params) + " " + message

    color_note_key = _color_note_key(context, items)
    if color_note_key:
        message += " " + translate(color_note_key, language).format(**params)

    response["message"] = message + (AVAILABILITY_CTA[language] if stock_hint else "")
    return response