"""
13.10: «осталось мало размеров» — честный сигнал дефицита для призыва к действию.

Что знаем точно: в products каждый РАЗМЕР модели — отдельная строка; скрапер строки не удаляет,
а снимает (is_active = false), когда размер пропал с сайта (сайт показывает только размеры в продаже).
  было   = все размеры модели, которые мы видели (с 02.10);
  осталось = активные размеры.
Дефицит: было ≥ SCARCE_MIN_EVER и осталось 1..SCARCE_MAX_LEFT.
Чего НЕ знаем: количество пар — поэтому говорим только про размеры на сайте.
Замер 13.10: 23 таких модели из 9 515 (история короткая — со временем больше).
"""
from sqlalchemy import or_

from app.db.models import Product

SCARCE_MAX_LEFT = 2
SCARCE_MIN_EVER = 4


def page_of(url: str | None) -> str:
    return (url or "").split("?")[0]


def _size_key(size) -> tuple:
    try:
        return (0, float(str(size).replace(",", ".").split("-")[0].split("/")[0]), str(size))
    except ValueError:
        return (1, 0.0, str(size))


def scarce_sizes_by_page(db, pages: list[str]) -> dict[str, list[str]]:
    """{страница: оставшиеся размеры} — только для моделей с дефицитом."""
    pages = [page for page in dict.fromkeys(pages) if page]
    if db is None or not pages:
        return {}
    conditions = []
    for page in pages:
        conditions += [Product.product_url == page, Product.product_url.like(f"{page}?%")]
    rows = db.query(Product.product_url, Product.size, Product.is_active).filter(or_(*conditions)).all()

    ever, left = {}, {}
    for url, size, active in rows:
        page = page_of(url)
        ever[page] = ever.get(page, 0) + 1
        if active and size:
            left.setdefault(page, set()).add(str(size))
    return {page: sorted(left[page], key=_size_key) for page in left
            if ever.get(page, 0) >= SCARCE_MIN_EVER and 1 <= len(left[page]) <= SCARCE_MAX_LEFT}