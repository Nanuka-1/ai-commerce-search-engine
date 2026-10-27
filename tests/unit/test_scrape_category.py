import pytest
import requests
from unittest.mock import patch, Mock
from sqlalchemy.exc import IntegrityError

from ingestion.scrape_category import (
    get_product_sitemap_urls,
    get_all_product_urls,
    extract_product_details_from_html,
    build_product_variants,
    get_product_changes,
    save_product_variant,
    save_variant_safely,
    deactivate_missing_products,
    read_checkpoint,
    write_checkpoint,
    clear_checkpoint,
    RESUME_OVERLAP,
    _fetch_variants_safe,
    extract_sizes_from_html,
    get_base_sku,
    ProductIndex,
    load_product_index,
    commit_batch,
    append_scraped_skus,
    read_scraped_skus,
    clear_scraped_skus,
    build_change_rows,
)

from ingestion import scrape_category


def test_get_product_sitemap_urls():
    fake_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <sitemap><loc>https://topsport.ge/sitemaps/ka/sitemap-pages.xml</loc></sitemap>
        <sitemap><loc>https://topsport.ge/sitemaps/ka/sitemap-products-1.xml</loc></sitemap>
        <sitemap><loc>https://topsport.ge/sitemaps/ka/sitemap-products-2.xml</loc></sitemap>
        <sitemap><loc>https://topsport.ge/sitemaps/ka/sitemap-collections.xml</loc></sitemap>
    </sitemapindex>
    """

    mock_response = Mock()
    mock_response.content = fake_xml.encode("utf-8")
    mock_response.raise_for_status = Mock()

    with patch("ingestion.scrape_category.requests.get", return_value=mock_response):
        result = get_product_sitemap_urls()

    assert result == [
        "https://topsport.ge/sitemaps/ka/sitemap-products-1.xml",
        "https://topsport.ge/sitemaps/ka/sitemap-products-2.xml",
    ]


def test_get_all_product_urls():
    fake_index_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <sitemap><loc>https://topsport.ge/sitemaps/ka/sitemap-products-1.xml</loc></sitemap>
    </sitemapindex>
    """

    fake_products_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://topsport.ge/ka/product/nike-shoe-1</loc></url>
        <url><loc>https://topsport.ge/ka/product/adidas-shoe-2</loc></url>
    </urlset>
    """

    mock_index_response = Mock()
    mock_index_response.content = fake_index_xml.encode("utf-8")
    mock_index_response.raise_for_status = Mock()

    mock_products_response = Mock()
    mock_products_response.content = fake_products_xml.encode("utf-8")
    mock_products_response.raise_for_status = Mock()

    with patch(
        "ingestion.scrape_category.requests.get",
        side_effect=[mock_index_response, mock_products_response],
    ):
        result = get_all_product_urls()

    assert result == [
        "https://topsport.ge/ka/product/nike-shoe-1",
        "https://topsport.ge/ka/product/adidas-shoe-2",
    ]

def test_extract_product_details_from_html():
    html = """
    <h1 class="title-detail font-18">NIKE მამაკაცის სპორტული ფეხსაცმელი</h1>
    <div class="product-information">
        <div class="item">
            <div class="title">ბრენდი</div>
            <div class="info">Nike</div>
        </div>
        <div class="item">
            <div class="title">SKU</div>
            <div class="info">FZ5307-007-44</div>
        </div>
        <div class="item">
            <div class="title">კატეგორია</div>
            <div class="info">
                <a href="#">მამაკაცი</a>,
                <a href="#">მამაკაცის ფეხსაცმელი</a>,
                <a href="#">მამაკაცის სპორტული ფეხსაცმელი</a>
            </div>
        </div>
    </div>
    <div class="product-image-slider">
        <figure><img loading="lazy" src="https://cdn.example.com/uploads/143324/1.avif" alt="main"></figure>
        <figure><img loading="lazy" src="https://cdn.example.com/uploads/143325/2.avif" alt="second"></figure>
    </div>
    <span class="current-price text-brand">477,00&nbsp;₾</span>
    """

    result = extract_product_details_from_html(html)

    assert result["name"] == "NIKE მამაკაცის სპორტული ფეხსაცმელი"
    assert result["brand"] == "Nike"
    assert result["price"] == 477.0
    assert result["categories"] == [
        "მამაკაცი",
        "მამაკაცის ფეხსაცმელი",
        "მამაკაცის სპორტული ფეხსაცმელი",
    ]
    assert result["image_url"] == "https://cdn.example.com/uploads/143324/1.avif"

def test_build_product_variants():
    fake_html = "<html>fake page</html>"

    mock_response = Mock()
    mock_response.text = fake_html

    fake_details = {
        "name": "NIKE მამაკაცის სპორტული ფეხსაცმელი",
        "brand": "Nike",
        "price": 477.0,
        "categories": ["მამაკაცი", "მამაკაცის ფეხსაცმელი"],
        "image_url": "https://cdn.example.com/uploads/143324/1.avif",
    }

    with patch("ingestion.scrape_category.requests.get", return_value=mock_response), \
         patch("ingestion.scrape_category.extract_sku_from_html", return_value="FZ5307-007-44"), \
         patch("ingestion.scrape_category.extract_sizes_from_html", return_value=["44", "45"]), \
         patch("ingestion.scrape_category.extract_product_details_from_html", return_value=fake_details), \
         patch("ingestion.scrape_category.extract_product_intent", return_value=None):

        result = build_product_variants("https://topsport.ge/ka/product/nike-mamakatsis-sportuli-fekhsatsmeli-1643")

    assert len(result) == 2

    assert result[0]["sku"] == "FZ5307-007-44"
    assert result[0]["size"] == "44"
    assert result[0]["name"] == "NIKE მამაკაცის სპორტული ფეხსაცმელი"
    assert result[0]["category_slug"] == "მამაკაცი, მამაკაცის ფეხსაცმელი"
    assert result[0]["image_url"] == "https://cdn.example.com/uploads/143324/1.avif"

    assert result[1]["sku"] == "FZ5307-007-45"
    assert result[1]["size"] == "45"

from types import SimpleNamespace


def test_get_product_changes_no_changes():
    existing = SimpleNamespace(
        name="Nike Shoe", brand="Nike", price=477.0,
        category_slug="მამაკაცი", product_type="footwear", style_group="sport",
        sport_type="running", usage_type="daily",
        model_family="air max", color="black",
        image_url="https://cdn.example.com/1.avif",
        product_url="https://topsport.ge/ka/product/nike-shoe-1?size=44",
    )

    variant = {
        "name": "Nike Shoe", "brand": "Nike", "price": 477.0,
        "category_slug": "მამაკაცი", "product_type": "footwear", "style_group": "sport",
        "sport_type": "running", "usage_type": "daily",
        "model_family": "air max", "color": "black",
        "image_url": "https://cdn.example.com/1.avif",
        "product_url": "https://topsport.ge/ka/product/nike-shoe-1?size=44",
    }

    changes = get_product_changes(existing, variant)

    assert changes == {}


def test_get_product_changes_price_changed():
    existing = SimpleNamespace(
        name="Nike Shoe", brand="Nike", price=477.0,
        category_slug="მამაკაცი", product_type="footwear", style_group="sport",
        sport_type="running", usage_type="daily",
        model_family="air max", color="black",
        image_url="https://cdn.example.com/1.avif",
        product_url="https://topsport.ge/ka/product/nike-shoe-1?size=44",
    )

    variant = {
        "name": "Nike Shoe", "brand": "Nike", "price": 399.0,
        "category_slug": "მამაკაცი", "product_type": "footwear", "style_group": "sport",
        "sport_type": "running", "usage_type": "daily",
        "model_family": "air max", "color": "black",
        "image_url": "https://cdn.example.com/1.avif",
        "product_url": "https://topsport.ge/ka/product/nike-shoe-1?size=44",
    }

    changes = get_product_changes(existing, variant)

    assert changes == {"price": (477.0, 399.0)}


from app.db.models import Product


def _make_variant(sku="TEST-SKU-1", price=477.0, product_url="https://topsport.ge/ka/product/test-shoe-1?size=44"):
    return {
        "sku": sku,
        "name": "Test Shoe",
        "brand": "Nike",
        "price": price,
        "category_slug": "მამაკაცი",
        "product_type": "footwear",
        "style_group": "sport",
        "sport_type": "running",
        "usage_type": "daily",
        "model_family": "air max",
        "color": "black",
        "size": "44",
        "product_url": product_url,
        "image_url": "https://cdn.example.com/1.avif",
    }

def test_save_product_variant_creates_new(db):
    variant = _make_variant(
        sku="TEST-SKU-CREATE",
        product_url="https://topsport.ge/ka/product/test-shoe-create?size=44",
    )
    status = save_product_variant(db, variant)
    db.flush()

    assert status == "created"
    assert db.query(Product).filter(Product.sku == "TEST-SKU-CREATE").count() == 1


def test_save_product_variant_updates_changed_price(db):
    existing = Product(**_make_variant(
        sku="TEST-SKU-UPDATE", price=477.0,
        product_url="https://topsport.ge/ka/product/test-shoe-update?size=44",
    ), is_active=True)
    db.add(existing)
    db.commit()

    variant = _make_variant(
        sku="TEST-SKU-UPDATE", price=399.0,
        product_url="https://topsport.ge/ka/product/test-shoe-update?size=44",
    )
    status = save_product_variant(db, variant)

    assert status == "updated"
    assert existing.price == 399.0


def test_save_product_variant_reactivates_inactive(db):
    existing = Product(**_make_variant(
        sku="TEST-SKU-REACTIVATE",
        product_url="https://topsport.ge/ka/product/test-shoe-reactivate?size=44",
    ), is_active=False)
    db.add(existing)
    db.commit()

    variant = _make_variant(
        sku="TEST-SKU-REACTIVATE",
        product_url="https://topsport.ge/ka/product/test-shoe-reactivate?size=44",
    )
    status = save_product_variant(db, variant)

    assert status == "reactivated"
    assert existing.is_active is True

def test_save_product_variant_warns_on_sku_change(db, capsys):
    existing = Product(
        **_make_variant(sku="OLD-SKU-44", product_url="https://topsport.ge/ka/product/test-shoe-2?size=44"),
        is_active=True,
    )
    db.add(existing)
    db.commit()

    variant = _make_variant(sku="NEW-SKU-44", product_url="https://topsport.ge/ka/product/test-shoe-2?size=44")
    status = save_product_variant(db, variant)
    db.commit()

    captured = capsys.readouterr()
    assert status == "updated"
    assert "Смена SKU" in captured.out
    assert existing.sku == "NEW-SKU-44"
    assert db.query(Product).filter(
        Product.product_url == "https://topsport.ge/ka/product/test-shoe-2?size=44"
    ).count() == 1


def test_deactivate_missing_products_deactivates_unscraped(db):
    existing_active_skus = {p.sku for p in db.query(Product).filter(Product.is_active == True).all()}

    stay_active = Product(**_make_variant(
        sku="TEST-DEACT-STAY", product_url="https://topsport.ge/ka/product/test-deact-stay?size=44",
    ), is_active=True)
    to_deactivate = Product(**_make_variant(
        sku="TEST-DEACT-GONE", product_url="https://topsport.ge/ka/product/test-deact-gone?size=44",
    ), is_active=True)
    db.add_all([stay_active, to_deactivate])
    db.commit()

    scraped_skus = existing_active_skus | {"TEST-DEACT-STAY"}

    result = deactivate_missing_products(db, scraped_skus)
    db.flush()

    assert result["skipped"] is False
    assert result["deactivated_count"] >= 1

    product = db.query(Product).filter(Product.sku == "TEST-DEACT-GONE").first()
    assert product.is_active is False

    product = db.query(Product).filter(Product.sku == "TEST-DEACT-STAY").first()
    assert product.is_active is True

def test_deactivate_missing_products_skips_on_low_coverage(db, capsys):
    for i in range(10):
        db.add(Product(**_make_variant(
            sku=f"TEST-COVERAGE-{i}",
            product_url=f"https://topsport.ge/ka/product/test-coverage-{i}?size=44",
        ), is_active=True))
    db.commit()

    scraped_skus = {"TEST-COVERAGE-0"}

    result = deactivate_missing_products(db, scraped_skus)

    captured = capsys.readouterr()

    assert result["skipped"] is True
    assert result["deactivated_count"] == 0
    assert "ВНИМАНИЕ" in captured.out

    product = db.query(Product).filter(Product.sku == "TEST-COVERAGE-1").first()
    assert product.is_active is True


def test_checkpoint_write_read_clear(tmp_path, monkeypatch):
    checkpoint_file = tmp_path / "scrape_checkpoint.txt"
    monkeypatch.setattr("ingestion.scrape_category.CHECKPOINT_FILE", str(checkpoint_file))

    assert read_checkpoint() == 0

    write_checkpoint(4200)
    assert read_checkpoint() == 4200

    clear_checkpoint()
    assert read_checkpoint() == 0


def test_resume_overlap_calculation():
    checkpoint_index = 4200
    start_index = max(0, checkpoint_index - RESUME_OVERLAP)
    assert start_index == 4000

def test_save_variant_safely_handles_integrity_error(db):
    variant = _make_variant(sku="ANY-SKU", product_url="https://topsport.ge/any")
    failed_urls = []

    with patch(
        "ingestion.scrape_category.save_product_variant",
        side_effect=IntegrityError("stmt", {}, Exception("dup")),
    ):
        result = save_variant_safely(db, variant, "https://topsport.ge/any", failed_urls)

    assert result is None
    assert failed_urls == ["https://topsport.ge/any"]



def test_save_product_variant_no_warning_for_different_size(db, capsys):
    existing = _make_variant(sku="ABC-20", product_url="https://topsport.ge/ka/product/some-shoe")
    save_product_variant(db, existing)
    db.flush()

    new_size_variant = _make_variant(sku="ABC-46", product_url="https://topsport.ge/ka/product/some-shoe?size=46")
    save_product_variant(db, new_size_variant)

    captured = capsys.readouterr()
    assert "Смена SKU" not in captured.out


def test_fetch_variants_safe_returns_variants_on_success():
    with patch("ingestion.scrape_category.build_product_variants", return_value=[{"sku": "TEST-1"}]):
        variants, error = _fetch_variants_safe("https://topsport.ge/any")

    assert variants == [{"sku": "TEST-1"}]
    assert error is None


def test_fetch_variants_safe_captures_exception():
    with patch("ingestion.scrape_category.build_product_variants", side_effect=ValueError("boom")):
        variants, error = _fetch_variants_safe("https://topsport.ge/any")

    assert variants is None
    assert isinstance(error, ValueError)

def test_fetch_page_uses_shared_session_with_timeout():
    with patch.object(scrape_category.SESSION, "get") as mock_get:
        mock_get.return_value.text = "<html></html>"
        result = scrape_category.fetch_page("https://topsport.ge/test")

    assert result == "<html></html>"
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs.get("timeout") == scrape_category.REQUEST_TIMEOUT

def _size_block(*sizes: str) -> str:
    items = "".join(f'<li><a href="#">{size}</a></li>' for size in sizes)
    return (
        '<div class="attr-detail attr-size mb-15">'
        '<strong class="mr-10 attr-title">Size:</strong>'
        f'<ul class="list-filter size-filter font-small">{items}</ul>'
        "</div>"
    )


def test_extract_sizes_reads_letter_size_and_ignores_numbers_elsewhere():
    html = (
        "<html><body>"
        + _size_block("XS")
        + "<div class='related'>33 38 43 47 -70%</div>"
        + "</body></html>"
    )
    assert extract_sizes_from_html(html) == ["XS"]


def test_extract_sizes_reads_numeric_shoe_size():
    html = "<html><body>" + _size_block("41") + "</body></html>"
    assert extract_sizes_from_html(html) == ["41"]


def test_extract_sizes_reads_std_for_one_size_products():
    html = "<html><body>" + _size_block("STD") + "</body></html>"
    assert extract_sizes_from_html(html) == ["STD"]


def test_extract_sizes_returns_empty_when_no_size_block():
    html = "<html><body><p>Price 42 GEL, 36 items</p></body></html>"
    assert extract_sizes_from_html(html) == []




@pytest.mark.parametrize("raw_sku, sizes, expected", [
    ("CT2302-100-44", ["44", "44.5", "45"], "CT2302-100"),          # Nike обувь, код цвета сохранён
    ("CZ1181-011-2XL", ["2XL", "L", "M"], "CZ1181-011"),            # Nike одежда
    ("10001-309-43-44", ["43-44", "45-46"], "10001-309"),            # Crocs, размер с дефисом
    ("IB9934-11/12 YEARS", ["11/12 YEARS", "12/13 YEARS"], "IB9934"),  # детский размер с пробелом
    ("37611-One", ["One"], "37611"),                                 # one-size с суффиксом
    ("IB4486-146", ["41"], "IB4486-146"),                            # без суффикса, одиночный размер
    ("10006994", ["NOSIZE"], "10006994"),                            # без суффикса, NOSIZE
])
def test_get_base_sku_real_audit_cases(raw_sku, sizes, expected):
    assert get_base_sku(raw_sku, sizes) == expected


def _product_page(raw_sku: str, size_block_html: str) -> str:
    return (
        "<html><head>"
        '<script type="application/ld+json">'
        f'[{{"@type": "Product", "sku": "{raw_sku}"}}]'
        "</script></head><body>"
        '<h1 class="title-detail">Nike Test Product</h1>'
        f"{size_block_html}"
        "</body></html>"
    )


def test_build_product_variants_multi_size_page(monkeypatch):
    html = _product_page("CZ1181-011-2XL", _size_block("2XL", "L"))
    monkeypatch.setattr("ingestion.scrape_category.fetch_page", lambda url: html)

    variants = build_product_variants("https://topsport.ge/ka/product/test")

    assert [v["sku"] for v in variants] == ["CZ1181-011-2XL", "CZ1181-011-L"]
    assert [v["size"] for v in variants] == ["2XL", "L"]


def test_build_product_variants_encodes_size_in_url(monkeypatch):
    html = _product_page("IB9934-11/12 YEARS", _size_block("11/12 YEARS"))
    monkeypatch.setattr("ingestion.scrape_category.fetch_page", lambda url: html)

    variants = build_product_variants("https://topsport.ge/ka/product/test")

    assert variants[0]["sku"] == "IB9934-11/12 YEARS"
    assert variants[0]["product_url"] == "https://topsport.ge/ka/product/test?size=11/12%20YEARS"


@pytest.mark.parametrize("raw_sku, raw_size, expected_size", [
    ("JH1234-5,", "5,", "5"),          # мяч: сайт пишет "5," -> размер "5", не "5."
    ("IB4486-40,5", "40,5", "40.5"),   # полуразмер через запятую
])
def test_build_product_variants_normalizes_size_separators(monkeypatch, raw_sku, raw_size, expected_size):
    html = _product_page(raw_sku, _size_block(raw_size))
    monkeypatch.setattr("ingestion.scrape_category.fetch_page", lambda url: html)

    variants = build_product_variants("https://topsport.ge/ka/product/test")

    assert variants[0]["size"] == expected_size
    assert variants[0]["sku"].endswith(f"-{expected_size}")

def test_save_product_variant_unchanged_makes_no_db_calls():
    existing = Product(**_make_variant(sku="IDX-UNCHANGED"), is_active=True)
    index = ProductIndex([existing])
    db = Mock()

    status = save_product_variant(db, _make_variant(sku="IDX-UNCHANGED"), index)

    assert status == "unchanged"
    assert db.method_calls == []


def test_save_product_variant_created_is_added_to_index_no_duplicates():
    index = ProductIndex([])
    db = Mock()
    variant = _make_variant(sku="IDX-NEW", product_url="https://topsport.ge/ka/product/idx-new?size=44")

    first = save_product_variant(db, variant, index)
    second = save_product_variant(db, variant, index)

    assert first == "created"
    assert second == "unchanged"
    assert db.add.call_count == 1


def test_save_product_variant_detects_url_conflict_in_memory():
    owner = Product(**_make_variant(sku="IDX-A", product_url="https://topsport.ge/ka/product/idx-a?size=44"), is_active=True)
    other = Product(**_make_variant(sku="IDX-B", product_url="https://topsport.ge/ka/product/idx-b?size=44"), is_active=True)
    index = ProductIndex([owner, other])

    variant = _make_variant(sku="IDX-B", product_url="https://topsport.ge/ka/product/idx-a?size=44")
    status = save_product_variant(Mock(), variant, index)

    assert status == "conflict"
    assert other.product_url == "https://topsport.ge/ka/product/idx-b?size=44"


def test_commit_batch_retries_one_by_one_on_integrity_error():
    db = Mock()
    db.commit.side_effect = [IntegrityError("stmt", {}, Exception("dup")), None]
    batch = [(_make_variant(sku="B-1"), "u1"), (_make_variant(sku="B-2"), "u2")]

    with patch("ingestion.scrape_category.load_product_index", return_value="NEW_INDEX"), \
         patch("ingestion.scrape_category.save_variant_safely") as safe_save:
        result = commit_batch(db, batch, "OLD_INDEX", [])

    db.rollback.assert_called_once()
    assert safe_save.call_count == 2
    assert result == "NEW_INDEX"


def test_fetch_page_raises_on_http_error():
    with patch.object(scrape_category.SESSION, "get") as mock_get:
        mock_get.return_value.raise_for_status.side_effect = requests.HTTPError("404 Not Found")

        with pytest.raises(requests.HTTPError):
            scrape_category.fetch_page("https://topsport.ge/test")


def test_fetch_page_retries_after_timeout_and_succeeds():
    ok_response = Mock(status_code=200, text="<html>ok</html>")
    with patch.object(scrape_category.SESSION, "get", side_effect=[requests.Timeout(), ok_response]) as mock_get, \
         patch("ingestion.scrape_category.time.sleep") as mock_sleep:
        result = scrape_category.fetch_page("https://topsport.ge/test")

    assert result == "<html>ok</html>"
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()


def test_fetch_page_gives_up_after_all_retries():
    with patch.object(scrape_category.SESSION, "get", side_effect=requests.Timeout()) as mock_get, \
         patch("ingestion.scrape_category.time.sleep"):
        with pytest.raises(requests.Timeout):
            scrape_category.fetch_page("https://topsport.ge/test")

    assert mock_get.call_count == scrape_category.FETCH_RETRIES + 1


def test_fetch_page_retries_on_429_then_succeeds():
    throttled = Mock(status_code=429)
    ok_response = Mock(status_code=200, text="<html>ok</html>")
    with patch.object(scrape_category.SESSION, "get", side_effect=[throttled, ok_response]) as mock_get, \
         patch("ingestion.scrape_category.time.sleep"):
        result = scrape_category.fetch_page("https://topsport.ge/test")

    assert result == "<html>ok</html>"
    assert mock_get.call_count == 2


def test_deactivate_missing_products_works_in_chunks(db, monkeypatch):
    monkeypatch.setattr("ingestion.scrape_category.DEACTIVATION_CHUNK_SIZE", 2)
    # защиту от неполного прогона проверяет отдельный тест (_skips_on_low_coverage)
    monkeypatch.setattr("ingestion.scrape_category.MIN_SCRAPE_COVERAGE_RATIO", 0)
    existing_active_skus = {p.sku for p in db.query(Product).filter(Product.is_active == True).all()}

    for i in range(5):
        db.add(Product(**_make_variant(
            sku=f"TEST-CHUNK-GONE-{i}",
            product_url=f"https://topsport.ge/ka/product/test-chunk-gone-{i}?size=44",
        ), is_active=True))
    db.add(Product(**_make_variant(
        sku="TEST-CHUNK-STAY",
        product_url="https://topsport.ge/ka/product/test-chunk-stay?size=44",
    ), is_active=True))
    db.commit()

    result = deactivate_missing_products(db, existing_active_skus | {"TEST-CHUNK-STAY"})
    db.commit()

    assert result["deactivated_count"] == 5
    assert result["skipped"] is False
    assert db.query(Product).filter(
        Product.sku.like("TEST-CHUNK-GONE-%"), Product.is_active == True
    ).count() == 0
    assert db.query(Product).filter(Product.sku == "TEST-CHUNK-STAY").first().is_active is True


def test_scraped_skus_file_roundtrip(tmp_path, monkeypatch):
    skus_file = tmp_path / "scraped_skus.txt"
    monkeypatch.setattr("ingestion.scrape_category.SCRAPED_SKUS_FILE", str(skus_file))

    assert read_scraped_skus() == set()

    append_scraped_skus({"CT2302-100-44", 'HB7461-M 7"'})
    append_scraped_skus({"IB9934-11/12 YEARS", "CT2302-100-44"})

    assert read_scraped_skus() == {"CT2302-100-44", 'HB7461-M 7"', "IB9934-11/12 YEARS"}

    clear_scraped_skus()
    assert read_scraped_skus() == set()


def test_change_log_records_created_with_price():
    change_log = []
    variant = _make_variant(sku="LOG-NEW", price=199.0, product_url="https://topsport.ge/ka/product/log-new?size=44")

    status = save_product_variant(Mock(), variant, ProductIndex([]), change_log)

    assert status == "created"
    assert change_log == [{"sku": "LOG-NEW", "change_type": "created", "new_value": "199.0", "new_price": 199.0}]


def test_change_log_records_price_decrease_with_numeric_prices():
    existing = Product(**_make_variant(sku="LOG-PRICE", price=390.0), is_active=True)
    change_log = []

    status = save_product_variant(Mock(), _make_variant(sku="LOG-PRICE", price=156.0),
                                  ProductIndex([existing]), change_log)

    assert status == "updated"
    assert change_log == [{
        "sku": "LOG-PRICE", "change_type": "updated", "field": "price",
        "old_value": "390.0", "new_value": "156.0", "old_price": 390.0, "new_price": 156.0,
    }]


def test_change_log_records_sku_change():
    existing = Product(**_make_variant(sku="IB4486-41", product_url="https://topsport.ge/ka/product/log-sku?size=41"),
                       is_active=True)
    change_log = []

    save_product_variant(Mock(), _make_variant(sku="IB4486-146-41", product_url="https://topsport.ge/ka/product/log-sku?size=41"),
                         ProductIndex([existing]), change_log)

    assert change_log[0] == {"sku": "IB4486-146-41", "change_type": "sku_changed", "field": "sku",
                             "old_value": "IB4486-41", "new_value": "IB4486-146-41"}


def test_change_log_empty_for_unchanged_product():
    existing = Product(**_make_variant(sku="LOG-SAME"), is_active=True)
    change_log = []

    save_product_variant(Mock(), _make_variant(sku="LOG-SAME"), ProductIndex([existing]), change_log)

    assert change_log == []


def test_build_change_rows_sets_run_id():
    rows = build_change_rows([{"sku": "A", "change_type": "created"}], run_id=7)

    assert rows[0].run_id == 7
    assert rows[0].sku == "A"
    assert rows[0].change_type == "created"


def test_deactivate_missing_products_returns_deactivated_skus(db, monkeypatch):
    monkeypatch.setattr("ingestion.scrape_category.MIN_SCRAPE_COVERAGE_RATIO", 0)
    existing_active_skus = {p.sku for p in db.query(Product).filter(Product.is_active == True).all()}
    db.add(Product(**_make_variant(sku="LOG-GONE", product_url="https://topsport.ge/ka/product/log-gone?size=44"),
                   is_active=True))
    db.commit()

    result = deactivate_missing_products(db, existing_active_skus)
    db.commit()

    assert "LOG-GONE" in result["deactivated_skus"]



# --- обычная (зачёркнутая) цена: разметка сайта 04.10 (view-source, Puma 177 -> 124 ₾, -30%) ---
_DISCOUNT_PRICE_BLOCK = """
<div class="clearfix product-price-cover">
    <div class="product-price primary-color float-left">
        <span class="current-price text-brand">124,00 ₾</span>
        <span class="old-price font-md ml-15">177,00 ₾</span>
        <span class="save-price font-md badge bg-danger text-white ml-15">-30%</span>
    </div>
</div>
"""

_NO_DISCOUNT_PRICE_BLOCK = """
<div class="clearfix product-price-cover">
    <div class="product-price primary-color float-left">
        <span class="current-price text-brand">399,00 ₾</span>
    </div>
</div>
"""


def test_extract_product_details_reads_regular_price_of_discounted_product():
    result = extract_product_details_from_html(_DISCOUNT_PRICE_BLOCK)

    assert result["price"] == 124.0
    assert result["regular_price"] == 177.0


def test_extract_product_details_without_discount_has_no_regular_price():
    # ниже на странице — "похожий товар" со своей скидкой: её брать нельзя
    related = '<div class="product-cart-wrap"><div class="product-price">' \
              '<span>99,00 ₾</span><span class="old-price">150,00 ₾</span></div></div>'

    result = extract_product_details_from_html(_NO_DISCOUNT_PRICE_BLOCK + related)

    assert result["price"] == 399.0
    assert result["regular_price"] is None


def test_get_product_changes_detects_discount_start():
    existing = Product(**_make_variant(sku="DISC-1"), is_active=True)
    variant = _make_variant(sku="DISC-1")
    variant["regular_price"] = 177.0

    changes = get_product_changes(existing, variant)

    assert changes["regular_price"] == (None, 177.0)