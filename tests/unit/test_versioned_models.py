import pytest

from app.services.intent_router import extract_size_from_query
from app.services.product_enrichment_service import VERSIONED_MODELS


@pytest.mark.parametrize("query, expected", [
    ("pegasus 41", None),            # версия есть в каталоге → размер не указан
    ("Pegasus 41", None),
    ("ultraboost 22", None),
    ("ub 23", None),
    ("pegasus 42", "42"),            # версии 42 в каталоге нет → это размер
    ("pegasus 40", "40"),
    ("nike pegasus 41 43", "43"),    # версия + размер
    ("air max 90 42", "42"),         # не версионная модель — как раньше
])
def test_number_after_model_is_version_only_if_in_catalog(query, expected):
    assert extract_size_from_query(query) == expected


def test_versioned_models_match_catalog_sql_07_10():
    assert VERSIONED_MODELS["pegasus"] == {"41"}
    assert VERSIONED_MODELS["ultraboost"] == {"21", "22"}