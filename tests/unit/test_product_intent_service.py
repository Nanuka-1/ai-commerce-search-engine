from app.services.product_intent_service import extract_product_intent
from app.schemas.product_classification import SportType, UsageType, StyleGroup


def test_extract_jordan_intent():
    intent = extract_product_intent("Nike Jordan shoes size 44")

    assert intent is not None
    assert intent.style_group == StyleGroup.BASKETBALL_LIFESTYLE
    assert intent.sport_type == SportType.BASKETBALL
    assert intent.usage_type == UsageType.LIFESTYLE


def test_extract_predator_intent():
    intent = extract_product_intent("Adidas Predator boots 42")

    assert intent is not None
    assert intent.style_group == StyleGroup.FOOTBALL_BOOTS
    assert intent.sport_type == SportType.FOOTBALL
    assert intent.usage_type == UsageType.PERFORMANCE


def test_extract_air_max_intent():
    intent = extract_product_intent("Nike Air Max black")

    assert intent is not None
    assert intent.style_group == StyleGroup.LIFESTYLE_SNEAKERS
    assert intent.sport_type == SportType.CASUAL
    assert intent.usage_type == UsageType.LIFESTYLE


def test_extract_category_based_footwear_intent():
    intent = extract_product_intent("Nike mamakatsis-sportuli-fekhsatsmeli")

    assert intent is not None
    assert intent.style_group == StyleGroup.LIFESTYLE_SNEAKERS
    assert intent.sport_type == SportType.CASUAL
    assert intent.usage_type == UsageType.LIFESTYLE


def test_unknown_product_returns_none():
    intent = extract_product_intent("random product")

    assert intent is None