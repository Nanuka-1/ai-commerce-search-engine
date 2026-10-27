"""
15.10: бюджет и скидка ПРАВИЛАМИ — мгновенно и без ИИ («Rules first»).
Самые частые формы: «200 ლარამდე», «200-მდე», «up to 200», «200 GEL», «ფასდაკლებით», «on sale».
21.10: «ახალი / ახალი კოლექცია / სიახლე / new collection / new arrivals» → только новинки (products.is_new).
Сложное («добавим 10 лари», «подешевле») по-прежнему понимает ИИ. Если ИИ не успел / недоступен,
бюджет, скидка и новинки всё равно соблюдаются.
"""
import re
from dataclasses import dataclass

NUMBER = r"(\d+(?:[.,]\d+)?)"
CURRENCY = r"(?:ლარ[ა-ჰ]*|₾|gel\b|lari\b)"

# «200 ლარამდე», «200 ლარის ფარგლებში», «200₾-მდე», «200 GEL», «200 ლარი»
PRICE_WITH_CURRENCY = re.compile(rf"{NUMBER}\s*{CURRENCY}(?:\s*-?\s*მდე)?(?:\s+ფარგლებში)?", re.IGNORECASE)
# «200-მდე», «200მდე» — без валюты; только числа от 50, чтобы не спутать с размером («42-მდე»)
PRICE_UNTIL = re.compile(rf"{NUMBER}\s*-?\s*მდე(?![ა-ჰ])", re.IGNORECASE)
# «up to 200», «under 200», «less than 200», «cheaper than 200», «maximum 200», «მაქსიმუმ 200»
# (не «max 42»: это модель Nike Air Max + размер)
PRICE_AFTER_WORD = re.compile(
    rf"(?:up to|under|below|less than|cheaper than|maximum|მაქსიმუმ)\s*{NUMBER}(?:\s*{CURRENCY})?",
    re.IGNORECASE)
MIN_PRICE_WITHOUT_CURRENCY = 50

DISCOUNT = re.compile(r"ფასდაკლ[ა-ჰ]*|\bon sale\b|\bsale\b|\bdiscount(?:ed|s)?\b", re.IGNORECASE)
FIRST = re.compile(r"პირველ[ა-ჰ]*|ჯერ\b|\bfirst\b", re.IGNORECASE)

# 21.10: новинки. Сначала длинные формы («ახალი კოლექცია»), потом одиночные слова.
# «ახლა» (сейчас) не задевается: корень «ახალ». «new balance» — бренд, не новинка.
NEW_ITEMS = re.compile(
    r"ახალ[ა-ჰ]*\s+კოლექც[ა-ჰ]*|ახალ[ა-ჰ]*|სიახლ[ა-ჰ]*"
    r"|\bnew\s+(?:collection|arrivals?|season)\b|\bnew\b(?!\s+balance)|\blatest\b",
    re.IGNORECASE)


@dataclass
class DealFilters:
    max_price: float | None = None
    discount_only: bool = False
    prefer_discount: bool = False
    new_only: bool = False       # 21.10: только новинки магазина
    cleaned: str = ""            # сообщение без слов о цене/скидке/новинках — для поиска по словам


def _to_number(text: str) -> float:
    return float(text.replace(",", "."))


def parse_deal_filters(message: str | None) -> DealFilters:
    text = (message or "").strip()
    result = DealFilters(cleaned=text)
    if not text:
        return result

    for pattern, needs_minimum in ((PRICE_AFTER_WORD, False), (PRICE_WITH_CURRENCY, False), (PRICE_UNTIL, True)):
        match = pattern.search(text)
        if match and (not needs_minimum or _to_number(match.group(1)) >= MIN_PRICE_WITHOUT_CURRENCY):
            result.max_price = _to_number(match.group(1))
            text = text[:match.start()] + " " + text[match.end():]
            break

    if DISCOUNT.search(text):
        if FIRST.search(text):
            result.prefer_discount = True        # «сначала со скидкой» — порядок, а не фильтр
            text = FIRST.sub(" ", text)
        else:
            result.discount_only = True
        text = DISCOUNT.sub(" ", text)

    if NEW_ITEMS.search(text):
        result.new_only = True
        text = NEW_ITEMS.sub(" ", text)

    result.cleaned = re.sub(r"\s+", " ", re.sub(r"[,;?!]+", " ", text)).strip()
    return result