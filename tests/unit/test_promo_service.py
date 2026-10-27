import json

from app.services.translations import translate

from app.db.models import Product
from app.services import cache_service
from app.services.promo_service import build_deals_response, discount_percent, get_ticker, load_config

PAGE = "https://topsport.ge/ka/product/"


def _add(db, sku, page, price, regular, active=True, size="42"):
    db.add(Product(sku=sku, name=f"Shoe {page}", brand="Nike", price=price, regular_price=regular,
                   category_slug="მამაკაცი", product_type="footwear", size=size,
                   product_url=f"{PAGE}{page}?size={size}", is_active=active))


def _fill(db):
    cache_service.clear()
    _add(db, "A-42", "a", 70.0, 100.0)                  # −30%
    _add(db, "A-43", "a", 60.0, 100.0, size="43")       # −40% — та же модель, берём лучший вариант
    _add(db, "B-42", "b", 90.0, 100.0)                  # −10% — ниже порога
    _add(db, "C-42", "c", 50.0, 100.0, active=False)    # −50%, но снят с продажи
    _add(db, "D-42", "d", 80.0, None)                   # без скидки
    _add(db, "E-42", "e", 75.0, 100.0)                  # −25%
    db.commit()


def test_discount_percent():
    assert discount_percent(70, 100) == 30
    assert discount_percent(100, 100) == 0
    assert discount_percent(80, None) == 0


def test_auto_deals_best_discount_per_model_only_active(db):
    _fill(db)
    ticker = get_ticker(db, "ka", {"mode": "auto_discounts", "limit": 8, "min_discount_percent": 20,
                                   "title": {"ka": "🔥 დღის ფასდაკლებები", "en": "🔥 Today's deals"}})
    assert ticker["title"] == "🔥 დღის ფასდაკლებები"
    assert ticker["sale_url"] == "https://topsport.ge/ka/products/sale"     # из настроек по умолчанию
    assert [(i["product_url"], i["discount_percent"]) for i in ticker["items"]] == [
        (f"{PAGE}a", 40), (f"{PAGE}e", 25)]


def test_manual_mode_keeps_marketing_order_and_skips_inactive(db):
    _fill(db)
    config = {"mode": "manual", "limit": 8, "manual_pages": [f"{PAGE}d", f"{PAGE}c", f"{PAGE}b?size=42"],
              "title": {"ka": "რეკლამა", "en": "Promo"}}
    ticker = get_ticker(db, "en", config)
    assert ticker["title"] == "Promo"
    assert [i["product_url"] for i in ticker["items"]] == [f"{PAGE}d", f"{PAGE}b"]   # c снят — пропущен


def test_broken_config_falls_back_to_defaults(tmp_path):
    bad = tmp_path / "promo.json"
    bad.write_text("{ это не json", encoding="utf-8")
    assert load_config(bad)["mode"] == "auto_discounts"
    good = tmp_path / "ok.json"
    good.write_text(json.dumps({"mode": "manual", "manual_pages": ["x"]}), encoding="utf-8")
    assert load_config(good)["mode"] == "manual" and load_config(good)["limit"] == 8


# --- «свежие скидки» (12.10): подешевели в последнем завершённом прогоне скрапера ---

from sqlalchemy import text

from app.services.promo_service import drop_percent, select_fresh_drops


def _run(db, run_id, started, finished):
    db.execute(text(
        "INSERT INTO scrape_runs (id, started_at, finished_at, resumed, urls_total, urls_failed, created_count, "
        "updated_count, reactivated_count, unchanged_count, conflict_count, deactivated_count) "
        "VALUES (:id, :started, :finished, :resumed, 0, 0, 0, 0, 0, 0, 0, 0)"),
        {"id": run_id, "started": started, "finished": finished, "resumed": False})


def _price_change(db, run_id, sku, old, new):
    db.execute(text(
        "INSERT INTO product_changes (run_id, sku, change_type, field, old_value, new_value, old_price, new_price, "
        "changed_at) VALUES (:run, :sku, 'updated', 'price', :old_v, :new_v, :old, :new, :at)"),
        {"run": run_id, "sku": sku, "old_v": str(old), "new_v": str(new), "old": old, "new": new,
         "at": "2026-10-09 10:00:00"})


def _fill_drops(db):
    cache_service.clear()
    _add(db, "F-42", "f", 99.0, None)                  # 222 → 99 (−55%)
    _add(db, "F-43", "f", 99.0, None, size="43")       # та же модель — одна карточка
    _add(db, "G-42", "g", 70.0, None)                  # 100 → 70 (−30%)
    _add(db, "H-42", "h", 95.0, None)                  # 100 → 95 (−5%) — ниже порога
    _add(db, "I-42", "i", 60.0, None, active=False)    # снят с продажи
    _add(db, "J-42", "j", 120.0, None)                 # в прогоне 100 → 80, но цена уже снова 120
    _run(db, 1, "2026-10-05 11:00:00", "2026-10-05 12:00:00")
    _run(db, 2, "2026-10-09 09:14:19", "2026-10-09 10:23:35")
    _run(db, 3, "2026-10-12 08:00:00", None)           # не завершён — не учитываем
    _price_change(db, 1, "G-42", 300.0, 100.0)         # старый прогон — не учитываем
    for sku in ("F-42", "F-43"):
        _price_change(db, 2, sku, 222.0, 99.0)
    _price_change(db, 2, "G-42", 100.0, 70.0)
    _price_change(db, 2, "H-42", 100.0, 95.0)
    _price_change(db, 2, "I-42", 100.0, 60.0)
    _price_change(db, 2, "J-42", 100.0, 80.0)
    _price_change(db, 3, "H-42", 95.0, 10.0)           # незавершённый прогон
    db.commit()


def test_drop_percent():
    assert drop_percent(222, 99) == 55
    assert drop_percent(100, 100) == 0
    assert drop_percent(None, 50) == 0


def test_fresh_drops_latest_finished_run_honest(db):
    _fill_drops(db)
    items, since = select_fresh_drops(db, limit=8, min_drop_percent=10)
    assert since == "2026-10-09"
    assert [(i["product_url"], i["old_price"], i["price"], i["drop_percent"]) for i in items] == [
        (f"{PAGE}f", 222.0, 99.0, 55), (f"{PAGE}g", 100.0, 70.0, 30)]


def test_ticker_fresh_drops_mode_returns_since(db):
    _fill_drops(db)
    ticker = get_ticker(db, "ka", {"mode": "fresh_drops", "limit": 1, "min_drop_percent": 10,
                                   "title": {"ka": "📉 ახალი ფასდაკლებები", "en": "📉 New price drops"}})
    assert ticker["mode"] == "fresh_drops" and ticker["since"] == "2026-10-09"
    assert [i["product_url"] for i in ticker["items"]] == [f"{PAGE}f"]


def test_no_finished_runs_empty(db):
    cache_service.clear()
    assert select_fresh_drops(db, limit=8, min_drop_percent=10) == ([], None)



# --- подборка пачками для кнопки виджета (12.10) ---

DEALS_CONFIG = {"min_drop_percent": 10, "min_discount_percent": 20,
                "sale_url": {"ka": "https://topsport.ge/ka/products/sale"}}


def test_deals_in_batches_with_sizes(db):
    _fill(db)                                   # прогонов нет → самые большие скидки: a (−40%), e (−25%)
    first = build_deals_response(db, "u", "ka", limit=1, offset=0, config=DEALS_CONFIG)
    results = first["data"]["results"]
    assert [i["product_url"] for i in results["items"]] == [f"{PAGE}a"]
    assert results["items"][0]["sizes"] == ["42", "43"]        # оба размера модели со скидкой
    assert results["has_more"] is True and results["total"] == 2

    second = build_deals_response(db, "u", "ka", limit=1, offset=1, config=DEALS_CONFIG)
    assert [i["product_url"] for i in second["data"]["results"]["items"]] == [f"{PAGE}e"]
    assert second["data"]["results"]["has_more"] is False

    third = build_deals_response(db, "u", "ka", limit=1, offset=2, config=DEALS_CONFIG)
    assert third["data"]["results"]["items"] == []
    assert third["message"] == translate("deals_no_more", "ka")