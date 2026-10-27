from eval_search import check_case


def _item(**fields):
    base = {"name": "Nike Air Max 90", "brand": "Nike", "size": "42",
            "category_slug": "მამაკაცი, ფეხსაცმელი", "color": "black"}
    base.update(fields)
    return base


def test_check_case_passes_when_all_top_items_match():
    case = {"query": "nike 42", "brand": "Nike", "size": "42", "name": "air max"}
    assert check_case(case, "found", [_item(), _item()]) == []


def test_check_case_reports_foreign_brand_and_wrong_size():
    case = {"query": "nike 42", "brand": "Nike", "size": "42"}
    problems = check_case(case, "found", [_item(brand="Puma", name="Puma RS-X", size="44")])
    assert "чужой бренд: Puma RS-X" in problems
    assert "размер 44: Puma RS-X" in problems


def test_check_case_accepts_crocs_range_size():
    case = {"query": "crocs 42", "brand": "Crocs", "size": "42"}
    assert check_case(case, "found", [_item(brand="Crocs", name="Crocs Clog", size="41-42")]) == []


def test_check_case_expected_mode_ignores_items():
    case = {"query": "pegasus", "mode": "need_size"}
    assert check_case(case, "need_size", []) == []
    assert check_case(case, "found", [_item()]) == ["режим found, ожидали need_size"]


def test_check_case_empty_result_fails():
    case = {"query": "nike 42", "brand": "Nike", "size": "42"}
    assert check_case(case, "not_found", []) == ["пусто (режим not_found)"]


def test_check_case_category_allows_unisex_for_men():
    case = {"query": "მამაკაცის ფეხსაცმელი 43", "size": "43", "category": ["მამაკაც", "Unisex"]}
    items = [_item(size="43", category_slug="Unisex, ფეხსაცმელი")]
    assert check_case(case, "found", items) == []


def test_check_case_color_unknown_is_allowed_but_other_color_fails():
    case = {"query": "nike white 42", "brand": "Nike", "size": "42", "color": "white"}
    assert check_case(case, "found", [_item(color=None)]) == []
    assert check_case(case, "found", [_item(color="red", name="Nike Red")]) == ["цвет red: Nike Red"]


def test_check_case_semantic_running_needs_footwear_and_running_majority():
    case = {"query": "running shoes 42", "size": "42", "product_type": "footwear", "sport": "running"}
    running = [_item(product_type="footwear", sport_type="running") for _ in range(3)]
    casual = [_item(product_type="footwear", sport_type="casual") for _ in range(2)]
    assert check_case(case, "found", running + casual) == []

    mostly_casual = running[:1] + casual + casual
    assert check_case(case, "found", mostly_casual) == ["для 'running' только 1 из 5"]


def test_check_case_semantic_wrong_product_type_and_name():
    case = {"query": "warm jacket M", "size": "M", "name_any": ["ქურთუკ", "jacket"]}
    jacket = _item(name="Nike მამაკაცის ქურთუკი", size="M")
    hoodie = _item(name="Nike მამაკაცის ჯემპრი", size="M")
    assert check_case(case, "found", [jacket]) == []
    assert check_case(case, "found", [jacket, hoodie]) == ["не тот товар: Nike მამაკაცის ჯემპრი"]

from eval_search import source_summary


def test_source_summary_counts_sources_in_top():
    items = [{"source": "keyword"}] * 3 + [{"source": "both"}, {"source": "semantic"}]
    assert source_summary(items) == "т3 с1 о1"


def test_source_summary_detects_hybrid_off_and_empty():
    assert source_summary([{"sku": "A"}, {"sku": "B"}]) == "выкл"   # меток нет -> гибрид не работал
    assert source_summary([]) == "-"

def test_check_case_max_items_reports_extra_products():
    case = {"query": "31241503", "name": "puma", "max_items": 1}
    puma = _item(name="Puma ბოტასი", brand="Puma")
    assert check_case(case, "found", [puma]) == []
    assert check_case(case, "found", [puma, _item()]) == ["лишние товары: 2 вместо 1"]