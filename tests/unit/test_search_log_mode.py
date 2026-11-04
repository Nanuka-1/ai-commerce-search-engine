"""04.11: аналитика на Vercel пишется ДО ответа (после ответа программа может «замереть»), локально — в фоне."""
import pytest

from app.services import background_log_service as service


class FakeDb:
    def __init__(self, engine):
        self.engine, self.rolled_back = engine, False

    def get_bind(self):
        return self.engine

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


class FakeExecutor:
    def __init__(self):
        self.jobs = []

    def submit(self, job):
        self.jobs.append(job)


@pytest.fixture
def app_db(monkeypatch):
    engine = object()
    monkeypatch.setattr(service, "_app_database", lambda: (engine, lambda: FakeDb(engine)))
    executor = FakeExecutor()
    monkeypatch.setattr(service, "_executor", executor)
    return FakeDb(engine), executor


@pytest.mark.parametrize("env, expected", [
    ({}, "background"),
    ({"VERCEL": "1"}, "sync"),
    ({"SEARCH_LOG_MODE": "sync"}, "sync"),
    ({"VERCEL": "1", "SEARCH_LOG_MODE": "background"}, "background"),    # явная настройка сильнее
])
def test_log_mode(monkeypatch, env, expected):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("SEARCH_LOG_MODE", raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert service.log_mode() == expected


def test_sync_writes_before_response_in_same_session(monkeypatch, app_db):
    db, executor = app_db
    monkeypatch.setenv("SEARCH_LOG_MODE", "sync")
    written = []
    service.log_after_response(lambda db, **kwargs: written.append((db, kwargs["query"])), db, query="nike 42")
    assert written == [(db, "nike 42")] and executor.jobs == []           # сразу, та же сессия, без фона


def test_sync_failure_does_not_break_answer(monkeypatch, app_db):
    db, _ = app_db
    monkeypatch.setenv("SEARCH_LOG_MODE", "sync")

    def broken(db, **kwargs):
        raise RuntimeError("Neon недоступен")

    assert service.log_after_response(broken, db, query="nike") is None   # не падает
    assert db.rolled_back                                                 # сессия запроса снова рабочая


def test_background_mode_unchanged(monkeypatch, app_db):
    db, executor = app_db
    monkeypatch.setenv("SEARCH_LOG_MODE", "background")
    written = []
    service.log_after_response(lambda db, **kwargs: written.append(kwargs["query"]), db, query="nike")
    assert written == [] and len(executor.jobs) == 1                      # ушло в фон, как раньше
    executor.jobs[0]()
    assert written == ["nike"]