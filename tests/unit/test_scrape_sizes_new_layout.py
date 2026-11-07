"""08.11: сайт сменил вёрстку — размеры теперь кнопки ul.pd-sizes > button.pd-size."""
from ingestion.scrape_category import extract_sizes_from_html, get_base_sku


def _new_size_block(*sizes: str, active: str | None = None) -> str:
    items = "".join(
        f'<li><button type="button" class="pd-size{" active" if size == active else ""}">\n'
        f"    {size}\n</button></li>"
        for size in sizes
    )
    return (
        '<div class="pd-option-head"><span class="pd-option-title">Size:</span></div>'
        f'<ul class="pd-sizes">{items}</ul>'
    )


def test_new_layout_reads_all_sizes_in_page_order():
    html = "<html><body>" + _new_size_block("44.5", "45.5", "46", "40", active="44.5") + "</body></html>"
    assert extract_sizes_from_html(html) == ["44.5", "45.5", "46", "40"]


def test_new_layout_ignores_numbers_outside_size_block():
    html = ("<html><body>" + _new_size_block("M", "L")
            + "<div class='related'><button class='pd-size-old'>42</button> 33 38 -70%</div></body></html>")
    assert extract_sizes_from_html(html) == ["M", "L"]


def test_new_layout_removes_duplicates():
    html = "<html><body>" + _new_size_block("41", "41", "42") + "</body></html>"
    assert extract_sizes_from_html(html) == ["41", "42"]


def test_old_layout_still_works_as_fallback():
    html = ('<html><body><div class="attr-detail attr-size">'
            '<ul class="list-filter size-filter"><li><a href="#">XS</a></li><li><a href="#">S</a></li></ul>'
            "</div></body></html>")
    assert extract_sizes_from_html(html) == ["XS", "S"]


def test_base_sku_from_real_page_example():
    # Реальная страница 08.11: SKU в JSON-LD "IH8659-44.5", первая кнопка размера 44.5 → модель IH8659
    sizes = extract_sizes_from_html("<html><body>" + _new_size_block("44.5", "45.5", "46") + "</body></html>")
    assert get_base_sku("IH8659-44.5", sizes) == "IH8659"