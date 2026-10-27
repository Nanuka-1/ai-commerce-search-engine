from types import SimpleNamespace

import app.services.hybrid_search_service as hybrid
from app.services.hybrid_search_service import SEMANTIC_FLOOR, apply_hybrid, filter_semantic, rrf_fuse

URL = "https://topsport.ge/ka/product/"


def test_rrf_found_by_both_rises_to_top():
    fused = rrf_fuse(keyword_pages=["a", "b", "c"], semantic_pages=["c", "d"])
    assert fused[0][0] == "c" and fused[0][2] == "both"      # 3-й в точном + 1-й в смысловом
    sources = {page: source for page, _, source in fused}
    assert sources == {"a": "keyword", "b": "keyword", "c": "both", "d": "semantic"}


def test_rrf_keeps_keyword_order_when_semantic_empty():
    assert [page for page, _, _ in rrf_fuse(["a", "b"], [])] == ["a", "b"]


def test_filter_semantic_relative_threshold():
    results = [("good", 0.73), ("ok", 0.67), ("junk", 0.58)]
    assert filter_semantic(results, margin=0.08) == [("good", 0.73), ("ok", 0.67)]
    assert filter_semantic([]) == []


def _context(items, total=None):
    return SimpleNamespace(items=items, total_count=len(items) if total is None else total,
                           query="q", matched_by="query", retrieval_mode="keyword")


def _request(**fields):
    base = dict(size=None, offset=0, limit=5, raw_query="beach slippers")
    base.update(fields)
    return SimpleNamespace(**base)


POSTGRES_DB = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))


def test_disabled_returns_keyword_context_unchanged(monkeypatch):
    monkeypatch.delenv("SEMANTIC_SEARCH_ENABLED", raising=False)
    context = _context([{"product_url": f"{URL}a"}])
    assert apply_hybrid(POSTGRES_DB, _request(), context) is context


def test_sqlite_returns_keyword_context_unchanged(monkeypatch):
    monkeypatch.setenv("SEMANTIC_SEARCH_ENABLED", "true")
    sqlite_db = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    context = _context([{"product_url": f"{URL}a"}])
    assert apply_hybrid(sqlite_db, _request(), context) is context


def test_gemini_failure_falls_back_to_keyword(monkeypatch):
    monkeypatch.setenv("SEMANTIC_SEARCH_ENABLED", "true")

    def boom(*args, **kwargs):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(hybrid, "_semantic_results", boom)
    context = _context([{"product_url": f"{URL}a"}])
    assert apply_hybrid(POSTGRES_DB, _request(), context) is context


def test_hybrid_merges_marks_source_and_rescues_empty_keyword(monkeypatch):
    monkeypatch.setenv("SEMANTIC_SEARCH_ENABLED", "true")
    monkeypatch.setattr(hybrid, "_semantic_results",
                        lambda *a: [(f"{URL}slides", 0.66), (f"{URL}adilette", 0.65), (f"{URL}junk", 0.50)])
    monkeypatch.setattr(hybrid, "load_cards", lambda db, pages, sizes: {
        page: {"product_url": page, "name": page.rsplit("/", 1)[-1]} for page in pages})

    result = apply_hybrid(POSTGRES_DB, _request(), _context([], total=0))

    assert [item["name"] for item in result.items] == ["slides", "adilette"]   # мусор 0.50 отсечён
    assert all(item["source"] == "semantic" for item in result.items)
    assert result.items[0]["similarity"] == 0.66
    assert result.total_count == 2 and result.matched_by == "semantic"


# --- шаг 3.6b: когда смысловой поиск не нужен ---
import pytest

from app.services.hybrid_search_service import needs_semantic


@pytest.mark.parametrize("query, strategy, expected", [
    ("pegasus", "model_search", False),           # известная модель
    ("nike air max 90 42", "model_search", False),
    ("31241503", "broad_search", False),          # артикул
    ("CT2302-100", None, False),
    ("running shoes 42", "broad_search", True),   # смысл без названия модели
    ("warm jacket M", None, True),
    ("nike 42", "brand_size", True),
    ("სარბენი ფეხსაცმელი 42", None, True),
])
def test_needs_semantic(query, strategy, expected):
    assert needs_semantic(query, strategy) is expected


def _no_gemini(*args, **kwargs):
    raise AssertionError("Gemini не должен вызываться")


def test_model_search_skips_gemini(monkeypatch):
    monkeypatch.setenv("SEMANTIC_SEARCH_ENABLED", "true")
    monkeypatch.setattr(hybrid, "_semantic_results", _no_gemini)
    context = _context([{"product_url": f"{URL}pegasus"}])
    context.search_strategy = "model_search"
    assert apply_hybrid(POSTGRES_DB, _request(raw_query="pegasus 42"), context) is context


def test_sku_query_skips_gemini(monkeypatch):
    monkeypatch.setenv("SEMANTIC_SEARCH_ENABLED", "true")
    monkeypatch.setattr(hybrid, "_semantic_results", _no_gemini)
    context = _context([{"product_url": f"{URL}puma"}])
    assert apply_hybrid(POSTGRES_DB, _request(raw_query="31241503"), context) is context


def test_total_count_counts_semantic_additions(monkeypatch):
    # 09.10: точный нашёл 1 модель, смысловой добавил ещё — клиенту нельзя говорить "нашли одну"
    monkeypatch.setenv("SEMANTIC_SEARCH_ENABLED", "true")
    monkeypatch.setattr(hybrid, "_semantic_results",
                        lambda *a: [(f"{URL}b", 0.70), (f"{URL}c", 0.69)])
    monkeypatch.setattr(hybrid, "load_cards", lambda db, pages, sizes: {
        page: {"product_url": page, "name": page.rsplit("/", 1)[-1]} for page in pages})
    result = apply_hybrid(POSTGRES_DB, _request(raw_query="running shoes 42"), _context([{"product_url": f"{URL}a"}]))
    assert len(result.items) == 3 and result.total_count == 3

def test_filter_semantic_absolute_floor():
    # замер 12.10: "gamarjoba" 0.612, "rogor xar ?" 0.594 — мусор; "swimming" 0.641 — осмысленный
    junk_only = [("caps", 0.612), ("keychain", 0.594)]
    assert filter_semantic(junk_only) == []                       # всё ниже планки → смысловой ничего не добавит

    mixed = [("swim", 0.641), ("pool", 0.639), ("junk", 0.60)]
    assert filter_semantic(mixed) == [("swim", 0.641), ("pool", 0.639)]


def test_semantic_floor_value_between_junk_and_meaningful():
    assert 0.612 < SEMANTIC_FLOOR < 0.641