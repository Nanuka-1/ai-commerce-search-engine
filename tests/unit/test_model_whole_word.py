"""13.10: «samba» отдельным словом выше, чем «samba» внутри другого слова (SAMBAE — другая модель)."""
from types import SimpleNamespace

from app.services.product_ranking_service import has_whole_word, rank_products


def _product(name, sku):
    return SimpleNamespace(name=name, brand="Adidas", sku=sku, size="38", category_slug="ქალი",
                           style_group=None, color=None)


def test_whole_word_detection():
    assert has_whole_word("adidas ქალის სპორტული ფეხსაცმელი samba og w", "samba")
    assert not has_whole_word("adidas ქალის სპორტული ფეხსაცმელი sambae w", "samba")
    assert has_whole_word("nike air max 90", "air max")
    assert not has_whole_word("anything", None)


def test_samba_before_sambae():
    sambae = _product("Adidas SAMBAE W", "JI1349-37")                         # короче — раньше выигрывала
    samba = _product("Adidas ქალის სპორტული ფეხსაცმელი SAMBA OG W", "B75806-38")
    ranked = rank_products([sambae, samba], tokens=["samba"], normalized_query="samba", usage_type=None,
                           model_hint="samba", requested_size="38")
    assert ranked[0] is samba