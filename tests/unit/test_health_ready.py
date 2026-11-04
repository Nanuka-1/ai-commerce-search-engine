"""04.11: /health/ready — CD после выкладки проверяет, что база и Redis отвечают (200), иначе 503 → откат."""
import json

import app.main as main


class FakeConnection:
    def __init__(self, fail):
        self.fail = fail

    def __enter__(self):
        if self.fail:
            raise ConnectionError("Neon недоступен")
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement):
        return None


class FakeEngine:
    def __init__(self, fail=False):
        self.fail = fail

    def connect(self):
        return FakeConnection(self.fail)


class FakeRedis:
    def __init__(self, fail=False):
        self.fail = fail

    def ping(self):
        if self.fail:
            raise TimeoutError("Upstash не ответил")
        return True


def _call(monkeypatch, db_fail=False, backend="memory", redis_fail=False):
    monkeypatch.setattr(main, "engine", FakeEngine(db_fail))
    monkeypatch.setattr(main.cache_service, "CACHE_BACKEND", backend)
    monkeypatch.setattr(main.cache_service, "_get_redis_client", lambda: FakeRedis(redis_fail))
    response = main.health_ready()
    return response.status_code, json.loads(response.body)


def test_ready_when_database_answers(monkeypatch):
    status, body = _call(monkeypatch)
    assert status == 200 and body["checks"] == {"database": "ok"}


def test_not_ready_when_database_down(monkeypatch):
    status, body = _call(monkeypatch, db_fail=True)
    assert status == 503 and body["checks"]["database"].startswith("error")


def test_redis_checked_only_when_enabled(monkeypatch):
    status, body = _call(monkeypatch, backend="redis")
    assert status == 200 and body["checks"] == {"database": "ok", "redis": "ok"}
    status, body = _call(monkeypatch, backend="redis", redis_fail=True)
    assert status == 503 and body["checks"]["redis"] == "error: TimeoutError"


def test_simple_health_needs_no_database():
    assert main.health() == {"status": "ok"}