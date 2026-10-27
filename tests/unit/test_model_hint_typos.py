import pytest

from app.services.query_parser_service import extract_model_hint_from_query


@pytest.mark.parametrize("query, expected", [
    ("pegasus", "pegasus"),                      # точное написание — как раньше
    ("pegasos", "pegasus"),                      # опечатка (golden set, stage 3.4)
    ("nike pegassus 42", "pegasus"),             # лишняя буква
    ("gazele 40", "gazelle"),                    # пропущенная буква
    ("air froce 1 44", "air force"),             # перестановка в двухсловной модели
    ("superstr 40", "superstar"),
    ("ultrabost 42", "ultraboost"),
    ("classic clgo 42", "classic clog"),
    ("handbal spezial", "handball spezial"),
])
def test_model_hint_recognizes_typos(query, expected):
    assert extract_model_hint_from_query(query) == expected


@pytest.mark.parametrize("query", [
    "nike 42",
    "running shoes 42",
    "warm jacket M",
    "black hoodie",
    "kids shoes",
    "sneakers",
    "boots",
    "court",                                     # общее слово — не модель (п.29)
    "max",
    "ნაიკი 42",
    "ქალის ჯემპრი S",
    "31241503",
])
def test_model_hint_no_false_positives(query):
    assert extract_model_hint_from_query(query) is None