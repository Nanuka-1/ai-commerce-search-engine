from app.services.product_enrichment_service import extract_color, extract_model_family


def test_extract_color_finds_black():
    assert extract_color("Nike Air Max Black-001") == "black"


def test_extract_color_normalizes_grey_to_gray():
    assert extract_color("PUMA Skyrocket Grey-XYZ") == "gray"


def test_extract_color_finds_gray_directly():
    assert extract_color("Adidas Gray Running Shoe") == "gray"


def test_extract_color_finds_navy():
    assert extract_color("Crocs Classic Clog T Navy") == "navy"


def test_extract_color_finds_coffee():
    assert extract_color("Reebok Shorts Coffee-Mau") == "coffee"


def test_extract_color_returns_none_when_no_color_in_name():
    assert extract_color("Adidas Qalis Sportuli Fexsacmeli") is None


def test_extract_model_family_finds_air_max():
    assert extract_model_family("Nike Air Max 90") == "air max"


def test_extract_model_family_handles_hyphens_and_underscores():
    assert extract_model_family("Nike-Air-Max_90") == "air max"


def test_extract_model_family_returns_none_when_no_match():
    assert extract_model_family("Adidas Qalis Sportuli Fexsacmeli") is None