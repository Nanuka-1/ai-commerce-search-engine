"""U2.3 (12.10): «до N лари» и «только со скидкой» — фильтры в базе + порядок «большая скидка первой»."""
from types import SimpleNamespace

from app.db.models import Product
from app.repositories.product_repository import get_products_by_query, get_products_by_size
from app.schemas.search_request import SearchRequest
from app.services.product_service import deal_filters, order_by_discount

PAGE = "https://topsport.ge/ka/product/"


def _add(db, sku, price, regular, size="33"):
    db.add(Product(sku=sku, name="Nike ბავშვის ფეხსაცმელი", brand="Nike", price=price, regular_price=regular,
                   category_slug="ბავშვი", product_type="footwear", size=size,
                   product_url=f"{PAGE}{sku.lower()}?size={size}", is_active=True))


def _fill(db):
    _add(db, "K-1", 60.0, 120.0)     # −50%
    _add(db, "K-2", 90.0, 100.0)     # −10%
    _add(db, "K-3", 150.0, None)     # без скидки, дорогой
    _add(db, "K-4", 80.0, 80.0)      # «старая» = текущая → не скидка
    db.commit()


def _skus(items):
    return sorted(product.sku for product in items)


def test_without_filters_nothing_changes(db):
    _fill(db)
    items, total = get_products_by_query(db, "ფეხსაცმელი")
    assert total == 4


def test_max_price(db):
    _fill(db)
    items, total = get_products_by_query(db, "ფეხსაცმელი", max_price=90)
    assert _skus(items) == ["K-1", "K-2", "K-4"] and total == 3


def test_discount_only(db):
    _fill(db)
    items, total = get_products_by_query(db, "ფეხსაცმელი", discount_only=True)
    assert _skus(items) == ["K-1", "K-2"] and total == 2


def test_budget_and_discount_together(db):
    _fill(db)
    items, total = get_products_by_query(db, "ფეხსაცმელი", max_price=70, discount_only=True)
    assert _skus(items) == ["K-1"]


def test_size_alternatives_respect_filters(db):
    _fill(db)
    items, total = get_products_by_size(db, size="33", discount_only=True)
    assert _skus(items) == ["K-1", "K-2"]


def test_biggest_discount_first():
    items = [SimpleNamespace(sku="a", price=90, regular_price=100),    # −10%
             SimpleNamespace(sku="b", price=60, regular_price=120),    # −50%
             SimpleNamespace(sku="c", price=50, regular_price=None)]   # без скидки
    assert [item.sku for item in order_by_discount(items, SearchRequest(raw_query="x", discount_only=True))] == ["b", "a", "c"]
    plain = SearchRequest(raw_query="x")
    assert order_by_discount(items, plain) is items          # без «со скидкой» — порядок ранжирования


def test_no_filter_arguments_without_filters():
    # без фильтров вызовы репозитория ровно как раньше
    assert deal_filters(SearchRequest(raw_query="x")) == {}
    assert deal_filters(SearchRequest(raw_query="x", max_price=100)) == {"max_price": 100.0, "discount_only": False}


def test_prefer_discount_orders_but_keeps_all():
    from app.services.product_service import prefer_discounted_cards
    items = [SimpleNamespace(sku="a", price=90, regular_price=None),       # без скидки
             SimpleNamespace(sku="b", price=60, regular_price=120)]        # −50%
    request = SearchRequest(raw_query="x", prefer_discount=True)
    assert [item.sku for item in order_by_discount(items, request)] == ["b", "a"]     # скидка первой, «a» не пропал
    context = SimpleNamespace(items=[{"name": "plain", "price": 90}, {"name": "sale", "price_from": 70, "regular_price": 140}])
    assert [card["name"] for card in prefer_discounted_cards(context, request).items] == ["sale", "plain"]
    assert prefer_discounted_cards(context, SearchRequest(raw_query="x")) is context    # без флага — как было