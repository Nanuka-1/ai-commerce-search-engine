from types import SimpleNamespace

from app.services.embedding_client import normalize
from app.services.embedding_text_service import text_hash
from ingestion.build_embeddings import (
    page_of,
    pick_page_cards,
    plan_embedding,
    select_pages_to_embed,
    to_vector_literal,
)

URL = "https://topsport.ge/ka/product/"


def _variant(id_, page, size):
    return SimpleNamespace(id=id_, product_url=f"{URL}{page}?size={size}")


def test_page_of_strips_size():
    assert page_of(f"{URL}pegasus?size=42") == f"{URL}pegasus"


def test_one_card_per_page_with_smallest_id():
    cards = pick_page_cards([_variant(7, "pegasus", "43"), _variant(3, "pegasus", "42"), _variant(5, "samba", "40")])
    assert set(cards) == {f"{URL}pegasus", f"{URL}samba"}
    assert cards[f"{URL}pegasus"].id == 3


def test_only_new_or_changed_pages_are_embedded():
    texts = {"a": "text a", "b": "text b NEW", "c": "text c", "d": "text d"}
    saved = {
        "a": (text_hash("text a"), "m1"),        # без изменений -> пропуск
        "b": (text_hash("text b"), "m1"),        # текст изменился -> пересчёт
        "c": (text_hash("text c"), "old-model"), # другая модель Gemini -> пересчёт
    }                                            # d нет в таблице -> посчитать
    assert select_pages_to_embed(texts, saved, "m1") == ["b", "c", "d"]


def test_vector_literal_format():
    assert to_vector_literal([0.5, -0.25]) == "[0.5000000,-0.2500000]"


def test_normalize_gives_unit_length():
    vector = normalize([3.0, 4.0])
    assert vector == [0.6, 0.8]
    assert normalize([0.0, 0.0]) == [0.0, 0.0]


def test_plan_copies_known_texts_and_counts_each_unique_text_once():
    texts = {
        "p1": "generic nike",   # 3 страницы с одинаковым текстом -> 1 текст для Gemini
        "p2": "generic nike",
        "p3": "generic nike",
        "p4": "pegasus",        # уникальный
        "p5": "samba",          # такой текст уже посчитан у p9 -> копия без Gemini
    }
    saved = {"p9": (text_hash("samba"), "m1")}

    copy_pages, new_groups, postponed = plan_embedding(texts, saved, "m1", budget=10)

    assert copy_pages == {"p5": text_hash("samba")}
    assert new_groups == [
        (text_hash("generic nike"), ["p1", "p2", "p3"]),   # самый частый текст первым
        (text_hash("pegasus"), ["p4"]),
    ]
    assert postponed == 0


def test_plan_respects_daily_budget():
    texts = {f"p{i}": f"text {i}" for i in range(5)}
    _, new_groups, postponed = plan_embedding(texts, {}, "m1", budget=2)
    assert len(new_groups) == 2
    assert postponed == 3


def test_plan_ignores_vectors_of_other_model():
    texts = {"p1": "samba"}
    saved = {"p9": (text_hash("samba"), "old-model")}   # другой моделью — копировать нельзя
    copy_pages, new_groups, _ = plan_embedding(texts, saved, "m1", budget=10)
    assert copy_pages == {}
    assert new_groups == [(text_hash("samba"), ["p1"])]