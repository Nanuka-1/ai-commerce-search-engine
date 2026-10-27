from types import SimpleNamespace

from app.services.product_grouping_service import group_variants_by_model
from app.services.product_serializer import serialize_model_cards, serialize_product

URL = "https://topsport.ge/ka/product/"


def _variant(page, size, price=399.0, sku=None):
    return SimpleNamespace(
        id=1, sku=sku or f"{page}-{size}", name=f"Nike {page}", brand="Nike", price=price, size=size,
        product_url=f"{URL}{page}?size={size}", is_active=True, category_slug="მამაკაცი", color=None,
    )


def test_variants_of_one_page_become_one_card_in_rank_order():
    ranked = [_variant("vomero", "43"), _variant("vomero", "42"), _variant("pegasus", "41"),
              _variant("vomero", "42.5")]

    cards = group_variants_by_model(ranked)

    assert [card.product.sku for card in cards] == ["vomero-43", "pegasus-41"]  # лучший вариант представляет модель
    assert cards[0].sizes == ["42", "42.5", "43"]
    assert cards[1].sizes == ["41"]


def test_card_price_from_is_minimum_price():
    cards = group_variants_by_model([_variant("samba", "40", 349.0), _variant("samba", "41", 299.0)])
    assert cards[0].price_from == 299.0


def test_sizes_sorted_numeric_crocs_and_letters():
    crocs = group_variants_by_model([_variant("clog", "45-46"), _variant("clog", "41-42"), _variant("clog", "36-37")])
    letters = group_variants_by_model([_variant("hoodie", "XL"), _variant("hoodie", "S"), _variant("hoodie", "M")])
    assert crocs[0].sizes == ["36-37", "41-42", "45-46"]
    assert letters[0].sizes == ["S", "M", "XL"]


def test_with_requested_size_nothing_is_merged():
    ranked = [_variant("a", "42"), _variant("b", "42"), _variant("c", "42")]
    assert len(group_variants_by_model(ranked)) == 3


def test_serialized_card_has_sizes_price_from_and_model_link():
    cards = group_variants_by_model([_variant("vomero", "42", 599.0), _variant("vomero", "43", 549.0)])

    data = serialize_model_cards(cards)[0]

    assert data["sizes"] == ["42", "43"]
    assert data["price_from"] == 549.0
    assert data["product_url"] == f"{URL}vomero"          # несколько размеров -> ссылка на модель


def test_single_size_card_keeps_size_link():
    data = serialize_model_cards(group_variants_by_model([_variant("vomero", "42")]))[0]
    assert data["product_url"] == f"{URL}vomero?size=42"


def test_serialize_product_includes_link_and_availability():
    data = serialize_product(_variant("vomero", "42"))
    assert data["product_url"] == f"{URL}vomero?size=42"
    assert data["available"] is True