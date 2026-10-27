"""21.10 (этап 3): «ახალი კოლექცია / new» → только новинки магазина (products.is_new)."""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Product
from app.repositories.product_repository import get_products_by_query
from app.services.deal_rules_service import parse_deal_filters
from app.services.product_service import deal_filters, has_deal_filters


@pytest.mark.parametrize("message, new_only, cleaned", [
    ("ახალი კოლექცია ქალის ფეხსაცმელი 36", True, "ქალის ფეხსაცმელი 36"),
    ("ქალის ახალი ფეხსაცმელი", True, "ქალის ფეხსაცმელი"),
    ("new arrivals nike 42", True, "nike 42"),
    ("სიახლეები", True, ""),
    ("new balance 42", False, "new balance 42"),       # бренд, не новинка
    ("nike 42", False, "nike 42"),
])
def test_new_items_words(message, new_only, cleaned):
    deal = parse_deal_filters(message)
    assert (deal.new_only, deal.cleaned) == (new_only, cleaned)


def test_new_only_is_a_search_filter():
    request = SimpleNamespace(new_only=True)
    assert has_deal_filters(request) is True
    assert deal_filters(request)["new_only"] is True


def test_repository_returns_only_new_products():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        Product(sku="A-36", name="ქალის ფეხსაცმელი A", size="36", product_url="u/a?size=36", is_new=True),
        Product(sku="B-36", name="ქალის ფეხსაცმელი B", size="36", product_url="u/b?size=36", is_new=False),
    ])
    db.commit()

    items, total = get_products_by_query(db, "ქალის ფეხსაცმელი", size="36", new_only=True)

    assert [item.sku for item in items] == ["A-36"]
    assert total == 1