"""16.10: вектор запроса считается в фоне, пока идёт точный поиск; Gemini зовём ОДИН раз."""
import time
from types import SimpleNamespace

import pytest

from app.services import cache_service, embedding_client
import app.services.hybrid_search_service as hybrid


def _slow_embed(calls, delay=0.2):
    def fake(texts, task_type, max_retries=5):
        calls.append(texts)
        time.sleep(delay)
        return [[0.6, 0.8]]
    return fake


def test_prefetch_then_embed_calls_gemini_once(monkeypatch):
    cache_service.clear()
    calls = []
    monkeypatch.setattr(embedding_client, "_embed", _slow_embed(calls))
    embedding_client.prefetch_query("ქალის ჯემპრი S")       # начали в фоне
    assert embedding_client.embed_query("ქალის ჯემპრი S") == [0.6, 0.8]   # дождались того же вызова
    assert len(calls) == 1


def test_prefetch_runs_in_background(monkeypatch):
    cache_service.clear()
    calls = []
    monkeypatch.setattr(embedding_client, "_embed", _slow_embed(calls, delay=0.5))
    started = time.perf_counter()
    embedding_client.prefetch_query("nike 42")
    assert time.perf_counter() - started < 0.2                # не ждём Gemini — точный поиск идёт параллельно
    time.sleep(0.7)
    assert cache_service.get(embedding_client.query_cache_key("nike 42")) == [0.6, 0.8]


def test_prefetch_skipped_when_vector_cached(monkeypatch):
    cache_service.clear()
    calls = []
    monkeypatch.setattr(embedding_client, "_embed", _slow_embed(calls))
    cache_service.set(embedding_client.query_cache_key("nike 42"), [0.1], ttl=60)
    embedding_client.prefetch_query("nike 42")
    assert calls == []


POSTGRES = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))


def _request(**overrides):
    values = dict(raw_query="ქალის ჯემპრი S", offset=0, max_price=None, discount_only=False)
    values.update(overrides)
    return SimpleNamespace(**values)


def test_prefetch_only_when_hybrid_will_be_used(monkeypatch):
    started = []
    monkeypatch.setattr(embedding_client, "prefetch_query", lambda text: started.append(text))
    monkeypatch.setenv("SEMANTIC_SEARCH_ENABLED", "true")

    hybrid.prefetch_query_vector(POSTGRES, _request(), "broad_search")
    assert started == ["ქალის ჯემპრი S"]

    for db, request, strategy in (
        (POSTGRES, _request(max_price=200.0), "broad_search"),       # бюджет — гибрида не будет
        (POSTGRES, _request(offset=5), "broad_search"),              # не первая страница
        (POSTGRES, _request(raw_query="pegasus 42"), "model_search"),  # точная модель
        (SimpleNamespace(bind=None), _request(), "broad_search"),    # не Postgres (тесты)
    ):
        hybrid.prefetch_query_vector(db, request, strategy)
    assert started == ["ქალის ჯემპრი S"]

    monkeypatch.setenv("SEMANTIC_SEARCH_ENABLED", "false")
    hybrid.prefetch_query_vector(POSTGRES, _request(), "broad_search")
    assert started == ["ქალის ჯემპრი S"]


def test_failed_background_call_is_reported_and_not_stuck(monkeypatch):
    # Gemini упал в фоне (лимит / сеть): ошибка доходит до смыслового поиска → apply_hybrid покажет поиск по словам;
    # ошибку не кэшируем, и следующий запрос пробует заново, а не «залипает» на упавшем вызове
    cache_service.clear()
    calls = []

    def broken(texts, task_type, max_retries=5):
        calls.append(texts)
        time.sleep(0.1)
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(embedding_client, "_embed", broken)
    embedding_client.prefetch_query("nike 42")
    with pytest.raises(RuntimeError):
        embedding_client.embed_query("nike 42")
    assert cache_service.get(embedding_client.query_cache_key("nike 42")) is None
    assert len(calls) == 1                                   # пока считалось — второй раз не звали

    monkeypatch.setattr(embedding_client, "_embed", _slow_embed(calls, delay=0))   # Gemini «ожил»
    assert embedding_client.embed_query("nike 42") == [0.6, 0.8]