"""16.10: запись аналитики после ответа — клиент не ждёт; тесты со своей базой пишут как раньше."""
import time
from types import SimpleNamespace

import app.services.background_log_service as service

APP_ENGINE = object()


class _FakeSession:
    def __init__(self, bind):
        self.bind, self.closed = bind, False

    def get_bind(self):
        return self.bind

    def close(self):
        self.closed = True


def _use_app_database(monkeypatch):
    sessions = []

    def factory():
        session = _FakeSession(APP_ENGINE)
        sessions.append(session)
        return session

    monkeypatch.setattr(service, "_app_database", lambda: (APP_ENGINE, factory))
    return sessions


def test_test_database_is_logged_immediately(monkeypatch):
    _use_app_database(monkeypatch)
    calls = []
    test_db = _FakeSession(bind="test-connection")            # тест / скрипт со своей базой
    service.log_after_response(lambda **kwargs: calls.append(kwargs), test_db, user_id="u", items=["x"])
    assert calls == [{"db": test_db, "user_id": "u", "items": ["x"]}]   # сразу и без изменений


def test_app_database_is_logged_in_background(monkeypatch):
    sessions = _use_app_database(monkeypatch)
    calls = []

    def slow_log(**kwargs):
        time.sleep(0.3)
        calls.append(kwargs)

    product = SimpleNamespace(sku="KB7843-S", name="Adidas ქალის ჯემპრი")
    context = SimpleNamespace(search_strategy="broad_search", matched_by="query", fallback_level=None, items=[product])
    started = time.perf_counter()
    service.log_after_response(slow_log, _FakeSession(APP_ENGINE), user_id="u", query="ქალის ჯემპრი S",
                               items=[product, {"sku": "IW9928-S"}], search_context=context,
                               ai_meta={"ai_used": True})
    assert time.perf_counter() - started < 0.1                 # ответ клиенту не ждёт запись
    time.sleep(0.5)
    logged = calls[0]
    assert logged["db"] is sessions[0] and sessions[0].closed  # своя сессия, закрыта после записи
    assert logged["items"] == [{"sku": "KB7843-S"}, {"sku": "IW9928-S"}]   # только простые значения
    assert logged["search_context"].search_strategy == "broad_search"
    assert logged["ai_meta"] == {"ai_used": True}


def test_background_error_does_not_break_chat(monkeypatch):
    sessions = _use_app_database(monkeypatch)

    def broken_log(**kwargs):
        raise RuntimeError("database is down")

    service.log_after_response(broken_log, _FakeSession(APP_ENGINE), user_id="u", items=[])   # не бросает
    time.sleep(0.2)
    assert sessions[0].closed