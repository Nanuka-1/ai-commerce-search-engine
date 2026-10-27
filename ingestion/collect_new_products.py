"""
21.10 (этап 3): «ახალი კოლექცია» — список новинок магазина → products.is_new.

Откуда: на сайте признак «новинка» есть только в фильтре списка https://topsport.ge/ka/products
(кнопка «ახალი კოლექცია»), на странице самого товара его нет → основной скрапер (sitemap → страницы товаров)
его не видит. Кнопка шлёт Livewire-запрос POST /livewire/update с calls=[setAttr("new")] — повторяем его
(разведка check_new_collection.py, журнал п.121): show=500 → порции по 500, gotoPage(n) → следующие порции.

Что делает:
  1. собирает страницы товаров (адрес без ?size) из фильтра «новые»;
  2. всем размерам этих моделей ставит is_new = true, остальным — false (одним COMMIT);
  3. если собрали подозрительно мало (сайт поменялся / ошибка) — НИЧЕГО не меняет, пишет предупреждение.

Запуск из корня проекта ПОСЛЕ основного скрапера:  python -m ingestion.collect_new_products
"""
import json
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.db.models import Product
from app.db.session import SessionLocal
from app.services import cache_service

BASE_URL = "https://topsport.ge"
LIST_URL = f"{BASE_URL}/ka/products"
UPDATE_URL = f"{BASE_URL}/livewire/update?locale=ka"
LIST_COMPONENT = "collection-page"
CHUNK_SIZE = 500                # товаров за один запрос (разведка: 500 → 2.6 МБ; 3000 → 10.6 МБ, грубо к сайту)
MAX_CHUNKS = 20                 # предохранитель от бесконечного цикла (20 × 500 = 10 000)
PAUSE_SECONDS = 1.5             # вежливо к сайту магазина
REQUEST_TIMEOUT = 60
MIN_NEW_PAGES = 100             # меньше — скорее сломался сбор, чем у магазина правда так мало новинок
UPDATE_CHUNK = 1000             # сколько id обновлять одним UPDATE


# --- разбор страниц (без сети — покрыто тестами) ---

def page_of(url: str) -> str:
    """Адрес страницы модели: без ?size=… и без / в конце (так же, как product_url в базе до '?')."""
    return (url or "").split("?")[0].rstrip("/")


def extract_livewire_state(html: str) -> tuple[str | None, str | None]:
    """(пропуск _token, состояние компонента списка товаров) со страницы /ka/products."""
    soup = BeautifulSoup(html, "html.parser")
    token = None
    meta = soup.find("meta", attrs={"name": "csrf-token"})
    if meta:
        token = meta.get("content")
    snapshot = None
    for tag in soup.find_all(attrs={"wire:snapshot": True}):
        data = json.loads(tag["wire:snapshot"])
        if data.get("memo", {}).get("name") == LIST_COMPONENT:
            snapshot = tag["wire:snapshot"]
            break
    return token, snapshot


def parse_card_pages(html: str) -> list[str]:
    """Страницы товаров из карточек списка (в порядке на странице, без повторов)."""
    soup = BeautifulSoup(html, "html.parser")
    pages = []
    for card in soup.select("div.product-cart-wrap"):
        link = card.find("a", href=re.compile(r"/product/"))
        if link:
            page = page_of(urljoin(BASE_URL, link["href"]))
            if page not in pages:
                pages.append(page)
    return pages


def parse_total(html: str) -> int | None:
    """«ნაპოვნია 2129 პროდუქტი» → 2129."""
    match = re.search(r"ნაპოვნია\s*(\d+)", BeautifulSoup(html, "html.parser").get_text(" "))
    return int(match.group(1)) if match else None


# --- сбор с сайта ---

def collect_pages(post_update, snapshot: str, pause: float = PAUSE_SECONDS) -> tuple[set[str], int | None]:
    """post_update(snapshot, calls, updates) -> (новый snapshot, html). Возвращает (страницы новинок, «ნაპოვნია»)."""
    snapshot, _ = post_update(snapshot, [{"path": "", "method": "setAttr", "params": ["new"]}], {})
    snapshot, html = post_update(snapshot, [], {"show": CHUNK_SIZE})
    total = parse_total(html)
    pages = set(parse_card_pages(html))

    for page_number in range(2, MAX_CHUNKS + 1):
        if total is not None and len(pages) >= total:
            break
        time.sleep(pause)
        snapshot, html = post_update(
            snapshot, [{"path": "", "method": "gotoPage", "params": [page_number, "page"]}], {})
        chunk = set(parse_card_pages(html))
        if not chunk - pages:
            break                                   # новых карточек нет — дошли до конца
        pages |= chunk
    return pages, total


def fetch_new_collection_pages() -> tuple[set[str], int | None]:
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    response = session.get(LIST_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    token, snapshot = extract_livewire_state(response.text)
    if not token or not snapshot:
        raise RuntimeError("на /ka/products не нашли _token или компонент списка (сайт изменился?)")

    def post_update(current_snapshot, calls, updates):
        body = {"_token": token,
                "components": [{"snapshot": current_snapshot, "updates": updates, "calls": calls}]}
        result = session.post(UPDATE_URL, json=body, timeout=REQUEST_TIMEOUT,
                              headers={"X-Livewire": "", "Referer": LIST_URL})
        result.raise_for_status()
        component = result.json()["components"][0]
        return component["snapshot"], component.get("effects", {}).get("html") or ""

    return collect_pages(post_update, snapshot)


# --- запись в базу ---

def apply_new_flags(db, new_pages: set[str], min_pages: int = MIN_NEW_PAGES) -> dict:
    """is_new = true у всех размеров моделей из new_pages, false у остальных. Один COMMIT.
    Собрали меньше min_pages → ничего не трогаем (лучше вчерашние новинки, чем пустой список)."""
    if len(new_pages) < min_pages:
        return {"skipped": True, "reason": f"собрано {len(new_pages)} страниц < {min_pages}"}

    rows = db.query(Product.id, Product.product_url, Product.is_new).all()
    to_true = [row.id for row in rows if page_of(row.product_url) in new_pages and not row.is_new]
    to_false = [row.id for row in rows if page_of(row.product_url) not in new_pages and row.is_new]
    matched_pages = {page_of(row.product_url) for row in rows} & new_pages

    for ids, value in ((to_true, True), (to_false, False)):
        for start in range(0, len(ids), UPDATE_CHUNK):
            chunk = ids[start:start + UPDATE_CHUNK]
            db.query(Product).filter(Product.id.in_(chunk)).update({Product.is_new: value},
                                                                    synchronize_session=False)
    db.commit()
    return {"skipped": False, "new_pages": len(new_pages), "matched_pages": len(matched_pages),
            "set_new": len(to_true), "unset_new": len(to_false)}


def main():
    started = time.perf_counter()
    try:
        pages, total = fetch_new_collection_pages()
    except Exception as error:
        print(f"⚠ Новинки не собраны, is_new не меняли: {error}")
        return
    print(f"С сайта: {len(pages)} страниц новинок (сайт пишет «ნაპოვნია {total}»), "
          f"{time.perf_counter() - started:.1f} с")
    if total and len(pages) < total * 0.9:
        print(f"⚠ Собрано заметно меньше, чем на сайте ({len(pages)} из {total}) — is_new не меняли.")
        return

    db = SessionLocal()
    try:
        result = apply_new_flags(db, pages)
    finally:
        db.close()
    if result["skipped"]:
        print(f"⚠ is_new не меняли: {result['reason']}")
        return
    print(f"Наших моделей среди новинок: {result['matched_pages']} из {result['new_pages']}; "
          f"стали новинкой: {result['set_new']} вариантов, перестали: {result['unset_new']}")
    if result["set_new"] or result["unset_new"]:
        cache_service.clear()


if __name__ == "__main__":
    main()