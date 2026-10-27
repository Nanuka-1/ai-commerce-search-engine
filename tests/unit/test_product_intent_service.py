
from app.services.product_intent_service import extract_product_intent, classify_product_type
from app.schemas.product_classification import ProductType, StyleGroup, SportType, UsageType

def test_classify_product_type_footwear():
    assert classify_product_type("მამაკაცი, მამაკაცის ფეხსაცმელი, მამაკაცის სპორტული ფეხსაცმელი") == ProductType.FOOTWEAR


def test_classify_product_type_clothing():
    assert classify_product_type("ქალი, ქალის ტანსაცმელი, ქალის მაისური") == ProductType.CLOTHING


def test_classify_product_type_accessory():
    assert classify_product_type("Unisex, აქსესუარები, ჩანთა") == ProductType.ACCESSORY


def test_classify_product_type_nutrition():
    assert classify_product_type("სპორტული კვება, ამინომჟავა") == ProductType.NUTRITION


def test_classify_product_type_equipment():
    assert classify_product_type("ჰობი და გართობა, სავარჯიშო მოწყობილობები, სავარჯიშო ველოსიპედი") == ProductType.EQUIPMENT


def test_classify_product_type_other_for_unknown_category():
    assert classify_product_type("სასაჩუქრე ვაუჩერი") == ProductType.OTHER


def test_classify_product_type_none_category():
    assert classify_product_type(None) == ProductType.OTHER


def test_extract_product_intent_specific_model_still_works():
    intent = extract_product_intent("Nike Air Jordan 1 Retro")
    assert intent.style_group == StyleGroup.BASKETBALL_LIFESTYLE
    assert intent.sport_type == SportType.BASKETBALL


def test_extract_product_intent_footwear_category_fallback():
    intent = extract_product_intent(
        "Adidas უცნობი მოდელი",
        category_slug="მამაკაცი, მამაკაცის ფეხსაცმელი, მამაკაცის სპორტული ფეხსაცმელი",
    )
    assert intent is not None
    assert intent.style_group is None
    assert intent.sport_type is None
    assert intent.usage_type == UsageType.PERFORMANCE


def test_extract_product_intent_non_footwear_returns_none():
    intent = extract_product_intent(
        "Adidas მაისური",
        category_slug="ქალი, ქალის ტანსაცმელი, ქალის მაისური",
    )
    assert intent is None
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
    intent = extract_product_intent(
        "Nike",
        category_slug="მამაკაცი, მამაკაცის ფეხსაცმელი, მამაკაცის სპორტული ფეხსაცმელი",
    )

    assert intent is not None
    assert intent.style_group is None
    assert intent.sport_type is None
    assert intent.usage_type == UsageType.PERFORMANCE


def test_unknown_product_returns_none():
    intent = extract_product_intent("random product")

    assert intent is None


def test_extract_product_intent_sport_category_returns_unknown_sport_type():
    result = extract_product_intent(
        "Nike ფეხსაცმელი",
        category_slug="მამაკაცი, მამაკაცის ფეხსაცმელი, მამაკაცის სპორტული ფეხსაცმელი",
    )
    assert result.sport_type is None
    assert result.usage_type == UsageType.PERFORMANCE


def test_extract_product_intent_casual_category_returns_casual():
    result = extract_product_intent(
        "Nike შლაპუნა",
        category_slug="მამაკაცი, მამაკაცის ფეხსაცმელი, მამაკაცის შლაპუნა",
    )
    assert result.sport_type == SportType.CASUAL
    assert result.usage_type == UsageType.LIFESTYLE


def test_extract_product_intent_specific_model_still_overrides_category():
    result = extract_product_intent(
        "Adidas Predator",
        category_slug="მამაკაცი, მამაკაცის ფეხსაცმელი, მამაკაცის სპორტული ფეხსაცმელი",
    )
    assert result.sport_type == SportType.FOOTBALL

def test_extract_product_intent_ignores_keyword_match_for_non_footwear():
    intent = extract_product_intent(
        "Under Armour Jordan Spieth Tour Adj Hat",
        category_slug="Unisex, აქსესუარები, ქუდი",
    )
    assert intent is None

def test_extract_product_intent_boots_category_returns_casual_lifestyle():
    intent = extract_product_intent("ბოტი", category_slug="მამაკაცის ბოტები")

    assert intent.style_group is None
    assert intent.sport_type == SportType.CASUAL
    assert intent.usage_type == UsageType.LIFESTYLE