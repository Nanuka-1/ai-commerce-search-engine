import pytest
from unittest.mock import patch

from app.services.intent_router import extract_size_from_query
from app.services.query_parser_service import extract_model_hint_from_query
from app.services.product_enrichment_service import extract_model_family
from ingestion.scrape_category import build_product_variants


@pytest.mark.parametrize("query, expected", [
    ("nike pegasus 41", None),
    ("pegasus 41 43", "43"),
    ("ultraboost 22", None),
    ("adidas ultraboost 22 42", "42"),
    ("air max 42", "42"),
    ("Air Max 90 42", "42"),
])
def test_version_numbers_are_not_sizes(query, expected):
    assert extract_size_from_query(query) == expected


@pytest.mark.parametrize("query, expected", [
    ("adidas samba 42", "samba"),
    ("superstar ii 40", "superstar"),
    ("crocs classic clog 41", "classic clog"),
    ("nike air force 1 44", "air force"),
    ("puma hoodie", None),
])
def test_model_hint_uses_catalog_models(query, expected):
    assert extract_model_hint_from_query(query) == expected


def test_scraper_and_search_share_model_list():
    assert extract_model_family("Adidas მამაკაცის სპორტული ფეხსაცმელი SAMBA OG") == "samba"


def test_comma_size_is_normalized():
    html = (
        '<html><head><script type="application/ld+json">[{"sku": "ABC-40,5"}]</script></head><body>'
        '<h1 class="title-detail">Test</h1>'
        '<div class="attr-detail attr-size"><ul class="list-filter size-filter">'
        '<li><a href="#">40,5</a></li></ul></div></body></html>'
    )
    with patch("ingestion.scrape_category.fetch_page", return_value=html):
        variants = build_product_variants("https://topsport.ge/ka/product/test")

    assert variants[0]["size"] == "40.5"
    assert variants[0]["sku"] == "ABC-40.5"