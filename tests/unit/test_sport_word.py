"""20.10 (экзамен): слово о виде спорта ищется и в названии, и в разметке sport_type."""
import pytest

from app.repositories.product_repository import sport_type_for_token, token_condition


@pytest.mark.parametrize("token, expected", [
    ("სარბენი", "running"),
    ("სარბენ", "running"),
    ("სირბილისთვის", "running"),
    ("Running", "running"),
    ("ფეხსაცმელი", None),
])
def test_sport_type_for_token(token, expected):
    assert sport_type_for_token(token) == expected


def _sql(condition) -> str:
    return str(condition.compile(compile_kwargs={"literal_binds": True}))


def test_sport_word_matches_sport_type_too():
    assert "sport_type" in _sql(token_condition("სარბენი"))


def test_ordinary_word_does_not_touch_sport_type():
    assert "sport_type" not in _sql(token_condition("ფეხსაცმელი"))