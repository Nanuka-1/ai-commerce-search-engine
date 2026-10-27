"""
20.10: разведка — можно ли забрать с сайта СПИСОК НОВИНОК («ახალი კოლექცია») так же, как это делает кнопка.

Кнопка на https://topsport.ge/ka/products шлёт POST /livewire/update с calls=[setAttr("new")].
Скрипт повторяет это и проверяет, как получить ВСЕ 2 129 новинок, а не первые 18:
  шаг 1 — включить фильтр «новые» (как кнопка);
  шаг 2 — попросить больше товаров за раз (updates.show = 100 / 500 / 3000) — какой максимум отдаёт сервер;
  шаг 3 — страница 2 (gotoPage / nextPage) — работает ли листание.
В нашу базу НИЧЕГО не пишет. Запуск из корня проекта: python check_new_collection.py
"""
import json
import re
import time

import requests
from bs4 import BeautifulSoup

BASE = "https://topsport.ge"
LIST_URL = f"{BASE}/ka/products"
UPDATE_URL = f"{BASE}/livewire/update?locale=ka"
PAUSE = 1.5                     # вежливо к сайту магазина

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0"


def find_list_component(html: str):
    """Ищем на странице компонент Livewire со списком товаров (у него в состоянии есть поле show)."""
    soup = BeautifulSoup(html, "html.parser")
    token = None
    meta = soup.find("meta", attrs={"name": "csrf-token"})
    if meta:
        token = meta.get("content")
    if not token:
        script = soup.find("script", attrs={"data-csrf": True})
        token = script.get("data-csrf") if script else None

    print("Компоненты Livewire на странице:")
    found = None
    for tag in soup.find_all(attrs={"wire:snapshot": True}):
        snapshot = json.loads(tag["wire:snapshot"])
        name = snapshot.get("memo", {}).get("name")
        keys = list(snapshot.get("data", {}).keys())
        print(f"  - {name}: {keys[:25]}")
        if "show" in snapshot.get("data", {}) and found is None:
            found = tag["wire:snapshot"]
    return token, found


def call_update(token: str, snapshot: str, calls=None, updates=None):
    body = {"_token": token,
            "components": [{"snapshot": snapshot, "updates": updates or {}, "calls": calls or []}]}
    response = session.post(UPDATE_URL, json=body, timeout=60,
                            headers={"X-Livewire": "", "Content-Type": "application/json",
                                     "Referer": LIST_URL})
    print(f"    HTTP {response.status_code}, {len(response.content) // 1024} КБ")
    response.raise_for_status()
    component = response.json()["components"][0]
    return component["snapshot"], component.get("effects", {}).get("html") or ""


def summary(label: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.product-cart-wrap")
    new_badges = sum(1 for card in cards if card.select_one("span.new"))
    links = []
    for card in cards:
        link = card.find("a", href=re.compile(r"/product/"))
        if link:
            links.append(link["href"].split("?")[0])
    total = re.search(r"ნაპოვნია\s*(\d+)", soup.get_text(" "))
    print(f"  {label}: карточек {len(cards)}, со значком «ახალი» {new_badges}, "
          f"«ნაპოვნია» {total.group(1) if total else '?'}; первые: {links[:2]}")
    return links


def main():
    page = session.get(LIST_URL, timeout=60)
    print(f"GET {LIST_URL}: HTTP {page.status_code}")
    token, snapshot = find_list_component(page.text)
    print(f"Пропуск (_token) найден: {bool(token)}; компонент списка найден: {bool(snapshot)}")
    if not token or not snapshot:
        print("Стоп: не нашли пропуск или компонент списка — пришлите вывод ассистенту.")
        return

    print("\nШаг 1 — фильтр «новые» (как кнопка):")
    snapshot, html = call_update(token, snapshot, calls=[{"path": "", "method": "setAttr", "params": ["new"]}])
    first_page = summary("новые, show=18", html)

    for show in (100, 500, 3000):
        time.sleep(PAUSE)
        print(f"\nШаг 2 — больше за раз: show={show}")
        try:
            _, html = call_update(token, snapshot, updates={"show": show})
            summary(f"новые, show={show}", html)
        except Exception as error:
            print(f"    не получилось: {error}")

    for method, params in (("gotoPage", [2, "page"]), ("nextPage", ["page"]), ("setPage", [2, "page"])):
        time.sleep(PAUSE)
        print(f"\nШаг 3 — страница 2 через {method}{params}:")
        try:
            _, html = call_update(token, snapshot, calls=[{"path": "", "method": method, "params": params}])
            links = summary(f"новые, {method}", html)
            print(f"    отличается от страницы 1: {bool(links) and links[:3] != first_page[:3]}")
        except Exception as error:
            print(f"    не получилось: {error}")


if __name__ == "__main__":
    main()