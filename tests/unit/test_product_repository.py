import pytest
from app.db.models import Product
from app.repositories.product_repository import (
    search_exact_model_products,
    search_same_brand_size_products,
    get_products_by_query,
    get_products_by_size,
    get_product_by_sku,
    size_variants
)


def _make_product(db, **overrides):
    defaults = dict(
        sku="TEST-SKU-1",
        name="Nike Air Max",
        brand="Nike",
        price=100.0,
        category_slug="shoes",
        size="42",
        product_url="https://topsport.ge/test-1",
        image_url=None,
        is_active=True,
    )
    defaults.update(overrides)
    product = Product(**defaults)
    db.add(product)
    db.flush()
    return product


def test_get_product_by_sku_excludes_inactive(db):
    _make_product(db, sku="INACTIVE-SKU", is_active=False, product_url="https://topsport.ge/inactive")

    result = get_product_by_sku(db, "INACTIVE-SKU")

    assert result is None


def test_get_products_by_size_excludes_inactive(db):
    _make_product(db, sku="ACTIVE-SIZE-42", size="42", is_active=True, product_url="https://topsport.ge/active-42")
    _make_product(db, sku="INACTIVE-SIZE-42", size="42", is_active=False, product_url="https://topsport.ge/inactive-42")

    results, total = get_products_by_size(db, size="42")

    skus = {p.sku for p in results}
    assert "ACTIVE-SIZE-42" in skus
    assert "INACTIVE-SIZE-42" not in skus


def test_search_exact_model_products_excludes_inactive(db):
    _make_product(db, sku="ACTIVE-MODEL", name="Adidas Superstar", is_active=True, product_url="https://topsport.ge/active-model")
    _make_product(db, sku="INACTIVE-MODEL", name="Adidas Superstar", is_active=False, product_url="https://topsport.ge/inactive-model")

    items, total = search_exact_model_products(db, model_hint="Superstar")

    skus = {p.sku for p in items}
    assert "ACTIVE-MODEL" in skus
    assert "INACTIVE-MODEL" not in skus


def test_search_same_brand_size_products_excludes_inactive(db):
    _make_product(db, sku="ACTIVE-BRAND", brand="Puma", is_active=True, product_url="https://topsport.ge/active-brand")
    _make_product(db, sku="INACTIVE-BRAND", brand="Puma", is_active=False, product_url="https://topsport.ge/inactive-brand")

    items, total = search_same_brand_size_products(db, brand="Puma")

    skus = {p.sku for p in items}
    assert "ACTIVE-BRAND" in skus
    assert "INACTIVE-BRAND" not in skus


def test_get_products_by_query_excludes_inactive(db):
    _make_product(db, sku="ACTIVE-QUERY", name="Reebok Classic", is_active=True, product_url="https://topsport.ge/active-query")
    _make_product(db, sku="INACTIVE-QUERY", name="Reebok Classic", is_active=False, product_url="https://topsport.ge/inactive-query")

    results, total = get_products_by_query(db, q="Reebok Classic")

    skus = {p.sku for p in results}
    assert "ACTIVE-QUERY" in skus
    assert "INACTIVE-QUERY" not in skus




def test_get_products_by_size_ignores_none_size_and_filters_by_category(db):
    product = Product(
        sku="TEST-SIZE-001",
        name="Test Product",
        brand="TestBrand",
        price=100.0,
        category_slug="mamakatsis-fexsacmeli",
        product_type="footwear",
        size="42",
        product_url="https://example.com/test-size-001",
        is_active=True,
    )
    db.add(product)
    db.commit()

    results, total_count = get_products_by_size(
        db=db,
        size=None,
        category="mamakatsis",
        limit=50,
    )

    assert total_count == 1
    assert results[0].sku == "TEST-SIZE-001"

@pytest.mark.parametrize("size, expected_subset", [
    ("M", {"M", "MD", "S/M", "M/L"}),
    ("m", {"M", "MD"}),
    ("XXL", {"XXL", "2XL"}),
    ("42", {"42", "41-42", "42-43"}),
    ("42.5", {"42.5"}),
])
def test_size_variants(size, expected_subset):
    assert expected_subset <= set(size_variants(size))


def test_size_variants_half_size_does_not_match_whole_size():
    assert "42" not in size_variants("42.5")


def test_get_products_by_size_matches_brand_specific_aliases(db):
    category = "test-size-alias-cat"
    db.add_all([
        Product(sku="SZ-UA-MD", name="UA Short", size="MD", category_slug=category,
                product_url="https://topsport.ge/ka/product/sz-ua?size=MD", is_active=True),
        Product(sku="SZ-ADI-M", name="Adidas Tee", size="M", category_slug=category,
                product_url="https://topsport.ge/ka/product/sz-adi?size=M", is_active=True),
        Product(sku="SZ-CROCS", name="Crocs Clog", size="41-42", category_slug=category,
                product_url="https://topsport.ge/ka/product/sz-crocs?size=41-42", is_active=True),
        Product(sku="SZ-NIKE-L", name="Nike Tee", size="L", category_slug=category,
                product_url="https://topsport.ge/ka/product/sz-nike?size=L", is_active=True),
    ])
    db.commit()

    m_items, _ = get_products_by_size(db, size="M", category=category)
    shoe_items, _ = get_products_by_size(db, size="42", category=category)

    assert {p.sku for p in m_items} == {"SZ-UA-MD", "SZ-ADI-M"}
    assert {p.sku for p in shoe_items} == {"SZ-CROCS"}

def test_category_filter_matches_georgian_categories_and_unisex_for_adults(db):
    size = "TSTCAT"
    db.add_all([
        Product(sku="CAT-MEN", name="Men Shoe", size=size,
                category_slug="მამაკაცი, მამაკაცის ფეხსაცმელი",
                product_url="https://topsport.ge/ka/product/cat-men", is_active=True),
        Product(sku="CAT-WOMEN", name="Women Shoe", size=size,
                category_slug="ქალი, ქალის ფეხსაცმელი",
                product_url="https://topsport.ge/ka/product/cat-women", is_active=True),
        Product(sku="CAT-UNISEX", name="Backpack", size=size,
                category_slug="Unisex, აქსესუარები",
                product_url="https://topsport.ge/ka/product/cat-unisex", is_active=True),
        Product(sku="CAT-KIDS", name="Kids Shoe", size=size,
                category_slug="ბავშვი, ბავშვის ფეხსაცმელი",
                product_url="https://topsport.ge/ka/product/cat-kids", is_active=True),
    ])
    db.commit()

    men, _ = get_products_by_size(db, size=size, category="მამაკაც")
    women, _ = get_products_by_size(db, size=size, category="ქალ")
    kids, _ = get_products_by_size(db, size=size, category="ბავშვ")

    assert {p.sku for p in men} == {"CAT-MEN", "CAT-UNISEX"}
    assert {p.sku for p in women} == {"CAT-WOMEN", "CAT-UNISEX"}
    assert {p.sku for p in kids} == {"CAT-KIDS"}