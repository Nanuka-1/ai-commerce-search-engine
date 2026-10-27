import pytest

from app.services.product_enrichment_service import infer_category_from_name
from app.services.product_intent_service import extract_product_intent, classify_product_type
from app.schemas.product_classification import ProductType, SportType


@pytest.mark.parametrize("name, expected_prefix", [
    ("Puma ბავშვის ბოტასი", "ბავშვი, "),
    ("Puma ქალის მაისური", "ქალი, "),
    ("Puma ბოტასი", "მამაკაცი, "),
    ("Puma მაისური", "მამაკაცი, "),
    ("Puma ჩანთა", "Unisex, "),
    ("Puma ქუდი", "Unisex, "),
])
def test_infer_category_from_name(name, expected_prefix):
    assert infer_category_from_name(name).startswith(expected_prefix)


def test_infer_category_from_name_handles_empty_name():
    assert infer_category_from_name(None) is None


def test_inferred_category_keeps_product_type():
    assert classify_product_type(infer_category_from_name("Puma ბოტასი")) == ProductType.FOOTWEAR
    assert classify_product_type(infer_category_from_name("Puma პლავკა")) == ProductType.CLOTHING


def test_sneakers_are_not_classified_as_boots():
    intent = extract_product_intent("puma", infer_category_from_name("Puma ბოტასი"))
    assert intent.sport_type != SportType.CASUAL


def test_boots_category_still_casual():
    intent = extract_product_intent("x", "მამაკაცის ბოტები")
    assert intent.sport_type == SportType.CASUAL