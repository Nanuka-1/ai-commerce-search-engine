"""15.10: бюджет и скидка правилами — работают даже если ИИ не успел."""
import pytest

from app.services.deal_rules_service import parse_deal_filters


@pytest.mark.parametrize("message, max_price, cleaned", [
    ("კაცის სარბენი 42, 200 ლარამდე?", 200.0, "კაცის სარბენი 42"),
    ("ბავშვის ფეხსაცმელი 36 100 ლარის ფარგლებში", 100.0, "ბავშვის ფეხსაცმელი 36"),
    ("nike 42 200-მდე", 200.0, "nike 42"),
    ("nike air max 42 cheaper than 300", 300.0, "nike air max 42"),
    ("running shoes under 150 GEL", 150.0, "running shoes"),
    ("ქურთუკი M 99.5₾", 99.5, "ქურთუკი M"),
    ("ქალის ჯემპრი მაქსიმუმ 120", 120.0, "ქალის ჯემპრი"),
])
def test_budget(message, max_price, cleaned):
    result = parse_deal_filters(message)
    assert result.max_price == max_price
    assert result.cleaned == cleaned


@pytest.mark.parametrize("message", ["nike 42", "ფეხსაცმელი 42-მდე", "adidas samba 38", "SKU CW2288-111",
                                     "nike air max 42"])
def test_no_budget_size_is_not_price(message):
    # размер и артикул — не бюджет
    assert parse_deal_filters(message).max_price is None


def test_discount_only_and_prefer_discount():
    only = parse_deal_filters("ქალის ქურთუკი M ფასდაკლებით")
    assert only.discount_only is True and only.prefer_discount is False
    assert only.cleaned == "ქალის ქურთუკი M"

    first = parse_deal_filters("adidas samba პირველ რიგში ფასდაკლებით")
    assert first.prefer_discount is True and first.discount_only is False

    both = parse_deal_filters("nike 42 on sale up to 200")
    assert both.discount_only is True and both.max_price == 200.0 and both.cleaned == "nike 42"


def test_empty_message():
    result = parse_deal_filters("  ")
    assert result.max_price is None and result.discount_only is False and result.cleaned == ""