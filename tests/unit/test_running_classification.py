import pytest

from app.schemas.product_classification import SportType, StyleGroup
from app.services.product_intent_service import extract_product_intent

MEN_SPORT_SHOES = "მამაკაცი, მამაკაცის ფეხსაცმელი, მამაკაცის სპორტული ფეხსაცმელი"
MEN_TSHIRT = "მამაკაცი, მამაკაცის ტანსაცმელი, მაისური"


@pytest.mark.parametrize("name", [
    "Nike მამაკაცის სპორტული ფეხსაცმელი AIR ZOOM PEGASUS 41",   # беговая модель
    "Adidas მამაკაცის სპორტული ფეხსაცმელი SUPERNOVA RISE",
    "Adidas მამაკაცის სპორტული ფეხსაცმელი ADIZERO SL",
    "Under Armour მამაკაცის სპორტული ფეხსაცმელი Charged Assert 10",
    "Nike მამაკაცის სპორტული ფეხსაცმელი Vomero Plus Men's Road Running Shoes",  # слово running
    "Nike მამაკაცის სარბენი ფეხსაცმელი",                         # грузинское "беговой"
])
def test_running_shoes_get_running_sport_type(name):
    intent = extract_product_intent(name, MEN_SPORT_SHOES)
    assert intent is not None
    assert intent.sport_type == SportType.RUNNING


def test_running_keyword_does_not_label_clothing():
    # "charged" есть и в названиях одежды UA — вид спорта ставим только обуви
    assert extract_product_intent("Under Armour მამაკაცის მაისური Charged Cotton", MEN_TSHIRT) is None


def test_existing_model_rules_unchanged():
    air_max = extract_product_intent("Nike Air Max 90", MEN_SPORT_SHOES)
    ultraboost = extract_product_intent("Adidas Ultraboost 22", MEN_SPORT_SHOES)
    assert air_max.sport_type == SportType.CASUAL
    assert ultraboost.style_group == StyleGroup.RUNNING_LIFESTYLE


def test_generic_sport_shoe_still_unknown_sport():
    intent = extract_product_intent("Nike მამაკაცის სპორტული ფეხსაცმელი", MEN_SPORT_SHOES)
    assert intent.sport_type is None

# --- 07.10: открытая обувь с беговым словом в названии — не беговая ---
MEN_SLIPPERS = "მამაკაცი, მამაკაცის ფეხსაცმელი, ჩუსტები"


@pytest.mark.parametrize("name, category", [
    ("Adidas ჩუსტი adiFOM SUPERNOVA", MEN_SLIPPERS),                 # шлёпанец по категории
    ("Adidas adiFOM SUPERNOVA", MEN_SPORT_SHOES),                    # adiFOM — не беговая линия
    ("Nike მამაკაცის სანდალი Revolution", MEN_SPORT_SHOES),          # сандалия по названию
    ("Puma Softride Slide", MEN_SPORT_SHOES),                        # slide по названию
])
def test_open_footwear_is_not_running(name, category):
    intent = extract_product_intent(name, category)
    assert intent is None or intent.sport_type != SportType.RUNNING


def test_slippers_category_falls_back_to_casual():
    intent = extract_product_intent("Adidas ჩუსტი adiFOM SUPERNOVA", MEN_SLIPPERS)
    assert intent.sport_type == SportType.CASUAL