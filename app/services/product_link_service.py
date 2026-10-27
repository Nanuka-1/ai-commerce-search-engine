"""
26.10 (этап 3, п.2): ссылка на товар topsport.ge в сообщении клиента.
Замер: чат читал адрес как слова — «adidas-bavshvis-jempri-25» → бренд adidas + РАЗМЕР 25 (номер страницы)
→ случайная детская обувь вместо джемпера. Ссылку узнаём правилом и ищем страницу в базе ТОЧНО.

В базе все адреса — /ka/ (замер 26.10: 10 000 страниц, 0 на /en/) → /en/ из ссылки клиента меняем на /ka/.
Адрес варианта в базе: «…/product/<slug>?size=36» → модель = адрес без «?size=…».
"""
import re
from dataclasses import dataclass
from urllib.parse import parse_qs

PRODUCT_LINK = re.compile(
    r"https?://(?:www\.)?topsport\.ge/(?:ka|en)/product/([\w\-.%]+)/?(?:\?([^\s#]*))?(?:#\S*)?",
    re.IGNORECASE,
)
CATALOG_PAGE = "https://topsport.ge/ka/product/{slug}"


@dataclass
class ProductLink:
    page: str               # адрес модели, как в базе: /ka/, без «?size=…»
    size: str | None        # размер из ссылки (?size=36), если был
    rest: str               # сообщение без ссылки: «ეს 38 ზომაში თუ გაქვთ?»


def find_product_link(message: str | None) -> ProductLink | None:
    """Первая ссылка на товар topsport.ge в сообщении или None (другие сайты, обычный текст)."""
    text = message or ""
    match = PRODUCT_LINK.search(text)
    if not match:
        return None
    size = (parse_qs(match.group(2) or "").get("size") or [None])[0]
    rest = " ".join((text[:match.start()] + " " + text[match.end():]).split())
    return ProductLink(page=CATALOG_PAGE.format(slug=match.group(1)), size=size, rest=rest)