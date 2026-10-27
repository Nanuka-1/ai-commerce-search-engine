"""21.10 (этап 3): сбор новинок магазина → products.is_new. Без сети: сайт подменён заглушкой."""
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Product
from ingestion.collect_new_products import (
    apply_new_flags,
    collect_pages,
    extract_livewire_state,
    page_of,
    parse_card_pages,
    parse_total,
)

BASE = "https://topsport.ge/ka/product"


def _card(slug: str, query: str = "") -> str:
    return (f'<div class="product-cart-wrap"><div class="product-badges"><span class="new">ახალი</span></div>'
            f'<a href="{BASE}/{slug}{query}">x</a></div>')


def _list_html(slugs, total=None) -> str:
    found = f"<p>ნაპოვნია {total} პროდუქტი</p>" if total is not None else ""
    return found + "".join(_card(slug) for slug in slugs)


def test_page_of_strips_size_and_trailing_slash():
    assert page_of(f"{BASE}/nike-a?size=42") == f"{BASE}/nike-a"
    assert page_of(f"{BASE}/nike-a/") == f"{BASE}/nike-a"


def test_parse_card_pages_unique_and_without_size():
    html = _card("nike-a", "?size=42") + _card("nike-a") + _card("adidas-b")
    assert parse_card_pages(html) == [f"{BASE}/nike-a", f"{BASE}/adidas-b"]


def test_parse_total():
    assert parse_total(_list_html([], total=2129)) == 2129
    assert parse_total("<p>nothing</p>") is None


def test_extract_livewire_state_finds_list_component():
    other = json.dumps({"memo": {"name": "components.cart"}, "data": {}})
    listing = json.dumps({"memo": {"name": "collection-page"}, "data": {"show": 18}})
    html = (f'<meta name="csrf-token" content="TOKEN"><div wire:snapshot=\'{other}\'></div>'
            f'<div wire:snapshot=\'{listing}\'></div>')
    token, snapshot = extract_livewire_state(html)
    assert token == "TOKEN"
    assert json.loads(snapshot)["memo"]["name"] == "collection-page"


def test_collect_pages_goes_through_chunks_until_total():
    calls = []
    chunks = {1: ["a", "b"], 2: ["c"], 3: ["c"]}         # 3-я порция ничего нового не дала бы

    def fake_post(snapshot, method_calls, updates):
        calls.append((method_calls, updates))
        if method_calls and method_calls[0]["method"] == "gotoPage":
            return "s", _list_html(chunks[method_calls[0]["params"][0]], total=3)
        if updates.get("show"):
            return "s", _list_html(chunks[1], total=3)
        return "s", ""                                      # setAttr("new")

    pages, total = collect_pages(fake_post, "start", pause=0)
    assert total == 3
    assert pages == {f"{BASE}/a", f"{BASE}/b", f"{BASE}/c"}
    assert calls[0][0][0]["params"] == ["new"]               # сначала фильтр «новые», как кнопка
    assert len(calls) == 3                                   # setAttr, show=500, gotoPage(2) — дальше не пошли


def _db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _product(db, slug: str, size: str, is_new=False):
    db.add(Product(sku=f"{slug}-{size}", name=slug, product_url=f"{BASE}/{slug}?size={size}",
                   is_active=True, is_new=is_new))


def _flags(db) -> dict:
    return {product.sku: product.is_new for product in db.query(Product).all()}


def test_apply_new_flags_marks_all_sizes_of_new_models_and_unmarks_old():
    db = _db()
    _product(db, "a", "40")
    _product(db, "a", "41")
    _product(db, "b", "42", is_new=True)                     # вчера была новинкой, сегодня нет
    db.commit()

    result = apply_new_flags(db, {f"{BASE}/a"}, min_pages=1)

    assert _flags(db) == {"a-40": True, "a-41": True, "b-42": False}
    assert (result["set_new"], result["unset_new"], result["matched_pages"]) == (2, 1, 1)


def test_apply_new_flags_does_nothing_when_too_few_pages_collected():
    db = _db()
    _product(db, "b", "42", is_new=True)
    db.commit()

    result = apply_new_flags(db, set(), min_pages=1)

    assert result["skipped"] is True
    assert _flags(db) == {"b-42": True}                      # сбор сломался → вчерашние новинки остались