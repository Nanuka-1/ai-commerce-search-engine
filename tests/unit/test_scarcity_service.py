"""13.10: дефицит размеров — было ≥ 4, осталось 1–2 (только по размерам на сайте)."""
from app.db.models import Product
from app.services.scarcity_service import scarce_sizes_by_page

PAGE = "https://topsport.ge/ka/product/"


def _add(db, page, size, active):
    db.add(Product(sku=f"{page}-{size}", name="Adidas მაისური", brand="Adidas", price=85.0, regular_price=122.0,
                   category_slug="ბავშვი", product_type="clothing", size=size,
                   product_url=f"{PAGE}{page}?size={size}", is_active=active))


def test_scarce_only_when_many_sizes_were_and_few_left(db):
    for size, active in (("36", False), ("37", False), ("38", True), ("39", False), ("40", True), ("41", False)):
        _add(db, "gazelle", size, active)                    # было 6, осталось 2 → дефицит
    for size, active in (("S", True), ("M", True)):
        _add(db, "small-model", size, active)                # было всего 2 — это не дефицит
    for size, active in (("S", True), ("M", True), ("L", True), ("XL", False)):
        _add(db, "plenty", size, active)                     # осталось 3 — не дефицит
    _add(db, "gazelle-2", "36", True)                        # похожий адрес — не путать с gazelle
    db.commit()
    result = scarce_sizes_by_page(db, [f"{PAGE}gazelle", f"{PAGE}small-model", f"{PAGE}plenty", f"{PAGE}gazelle-2"])
    assert result == {f"{PAGE}gazelle": ["38", "40"]}


def test_no_db_or_pages_is_empty():
    assert scarce_sizes_by_page(None, ["x"]) == {}