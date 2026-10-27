from types import SimpleNamespace

import pytest

import app.services.embedding_client as client
from app.services.embedding_client import DailyQuotaExceeded, embed_documents, embed_query, is_daily_quota_error

DAILY = "429 RESOURCE_EXHAUSTED quotaId: EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier"
MINUTE = "429 RESOURCE_EXHAUSTED quotaId: EmbedContentRequestsPerMinutePerUserPerProjectPerModel-FreeTier"


def _fake_gemini(monkeypatch, message):
    calls = []

    def embed_content(**kwargs):
        calls.append(kwargs)
        raise RuntimeError(message)

    monkeypatch.setattr(client, "_get_client", lambda: SimpleNamespace(models=SimpleNamespace(embed_content=embed_content)))
    return calls


def _no_sleep(seconds):
    raise AssertionError("не должны ждать")


def test_is_daily_quota_error():
    assert is_daily_quota_error(RuntimeError(DAILY))
    assert not is_daily_quota_error(RuntimeError(MINUTE))
    assert not is_daily_quota_error(RuntimeError("500 INTERNAL"))


def test_daily_quota_stops_immediately_without_waiting(monkeypatch):
    calls = _fake_gemini(monkeypatch, DAILY)
    monkeypatch.setattr(client.time, "sleep", _no_sleep)
    with pytest.raises(DailyQuotaExceeded):
        embed_documents(["Nike Pegasus 41"])
    assert len(calls) == 1          # одна попытка, без повторов


def test_minute_limit_still_waits_and_retries_for_catalog(monkeypatch):
    calls = _fake_gemini(monkeypatch, MINUTE)
    waits = []
    monkeypatch.setattr(client.time, "sleep", waits.append)
    with pytest.raises(RuntimeError):
        embed_documents(["Nike Pegasus 41"])
    assert len(calls) == client.MAX_RETRIES and len(waits) == client.MAX_RETRIES - 1


def test_client_query_does_not_wait_on_minute_limit(monkeypatch):
    calls = _fake_gemini(monkeypatch, MINUTE)
    monkeypatch.setattr(client.time, "sleep", _no_sleep)
    with pytest.raises(RuntimeError):
        embed_query("running shoes 42")
    assert len(calls) == 1          # чат не ждёт минуту — гибрид откатится на точный поиск