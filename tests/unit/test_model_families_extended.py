import pytest

from app.services.product_enrichment_service import extract_model_family
from app.services.query_parser_service import extract_model_hint_from_query


# Названия по образцу реального каталога (частотный SQL 04.10 по названиям без model_family)
@pytest.mark.parametrize("name, expected", [
    ("Puma ბოტასი Ferrari RS-X Mid", "rs x"),
    ("Puma ბოტასი Softride Pro Control", "softride"),
    ("Puma ბოტასი Explore NITRO 2 Mid", "nitro"),
    ("Crocs ჩუსტი InMotion Flip", "inmotion"),
    ("Crocs კლოგი Classic Crush Clog", "crush"),       # "classic ... clog" не подряд -> не classic clog
    ("Crocs კლოგი Echo Wave", "echo"),
    ("Crocs კლოგი Echo Clog", "echo clog"),             # более конкретная модель — раньше в списке
    ("Adidas TERREX AX4", "terrex"),
    ("Nike Court Vision Low", "court vision"),
    ("Under Armour ANSA Fix Slide", "ansa"),
    ("Nike მამაკაცის სპორტული ფეხსაცმელი", None),     # общее название — модели нет
])
def test_extract_model_family_new_catalog_models(name, expected):
    assert extract_model_family(name) == expected


@pytest.mark.parametrize("query, expected", [
    ("puma rs-x 42", "rs x"),                           # дефис в запросе = пробел, как в названиях
    ("softride 43", "softride"),
    ("terrex 44", "terrex"),
    ("nike court vision 42", "court vision"),
    ("crocs echo 42", "echo"),
    ("adidas forum low 42", "forum"),
])
def test_model_hint_new_catalog_models(query, expected):
    assert extract_model_hint_from_query(query) == expected


@pytest.mark.parametrize("query", ["mid", "low", "platform", "water", "road", "runner", "glitter", "kids"])
def test_model_hint_ignores_frequent_non_model_words(query):
    # частые слова из того же SQL, отброшенные как не-модели
    assert extract_model_hint_from_query(query) is None