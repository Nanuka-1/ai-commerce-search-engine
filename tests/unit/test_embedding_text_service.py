from types import SimpleNamespace

from app.services.embedding_text_service import build_embedding_text, text_hash


def _product(**fields):
    base = dict(
        name="Nike მამაკაცის სპორტული ფეხსაცმელი AIR ZOOM PEGASUS 41",
        brand="Nike",
        category_slug="მამაკაცი, მამაკაცის ფეხსაცმელი, მამაკაცის სპორტული ფეხსაცმელი",
        product_type="footwear",
        sport_type="running",
        model_family="pegasus",
        color="black",
    )
    base.update(fields)
    return SimpleNamespace(**base)


def test_full_card_text_has_name_and_english_anchors():
    text = build_embedding_text(_product())
    assert text == (
        "Nike მამაკაცის სპორტული ფეხსაცმელი AIR ZOOM PEGASUS 41 | brand: Nike | for: men"
        " | type: shoes, footwear | sport: running | model: pegasus | color: black"
    )


def test_unknown_fields_are_skipped():
    generic = _product(name="Nike მამაკაცის სპორტული ფეხსაცმელი", sport_type=None,
                       model_family=None, color=None)
    assert build_embedding_text(generic) == (
        "Nike მამაკაცის სპორტული ფეხსაცმელი | brand: Nike | for: men | type: shoes, footwear"
    )


def test_gender_from_category_kids_women_unisex():
    assert "for: kids" in build_embedding_text(_product(category_slug="ბავშვი, ბავშვის ფეხსაცმელი"))
    assert "for: women" in build_embedding_text(_product(category_slug="ქალი, ქალის ტანსაცმელი"))
    assert "for: unisex" in build_embedding_text(_product(category_slug="Unisex, ჩანთა"))


def test_size_and_price_not_in_text():
    product = _product()
    product.size, product.price = "42", 399.0
    text = build_embedding_text(product)
    assert "42" not in text.replace("PEGASUS 41", "") and "399" not in text


def test_text_hash_changes_only_when_text_changes():
    assert text_hash("a") == text_hash("a")
    assert text_hash("a") != text_hash("b")