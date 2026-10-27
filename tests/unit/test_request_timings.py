"""15.10: время по этапам сообщения → meta.timings; причина, если ИИ-понимание не сработало."""
import time

from app.services import request_timings


def test_timings_by_stage_in_meta():
    timings, token, started = request_timings.start()
    stage_started = time.perf_counter()
    time.sleep(0.05)                                    # «поиск шёл 50 мс»
    request_timings.record("search", stage_started)
    request_timings.record("ai_text", time.perf_counter())
    response = request_timings.finish({"type": "product_search", "meta": {"ai_used": True}}, timings, token, started)
    meta = response["meta"]
    assert meta["ai_used"] is True                         # старые поля meta на месте
    assert meta["timings"]["search"] >= 50
    assert set(meta["timings"]) == {"search", "ai_text", "other", "total"}
    assert meta["timings"]["total"] >= meta["timings"]["search"]
    assert "understanding_skipped" not in meta


def test_understanding_skipped_reason():
    for errors, reason in ((["timeout"], "timeout"), (["gemini: 503 UNAVAILABLE"], "gemini: 503 UNAVAILABLE"),
                           ([], "no_result")):
        timings, token, started = request_timings.start()
        request_timings.note_skipped(errors)
        response = request_timings.finish({"type": "product_search", "meta": None}, timings, token, started)
        assert response["meta"]["understanding_skipped"] == reason
        assert "_understanding_skipped" not in response["meta"]["timings"]


def test_outside_chat_request_does_nothing():
    request_timings.record("search", time.perf_counter())      # тесты / скрипты: без start() — не падает
    request_timings.note_skipped(["timeout"])


# --- 15.10 (шаг 2): этапы через with + журнал обращений к базе ---

class _FakeConn:
    def __init__(self):
        self.info = {}


def test_stage_and_sql_log():
    timings, token, started = request_timings.start()
    conn = _FakeConn()
    with request_timings.stage("session"):
        request_timings.before_sql(conn, None, "SELECT * FROM conversation_sessions WHERE user_id = %s", None, None, False)
        request_timings.after_sql(conn, None, "SELECT * FROM conversation_sessions WHERE user_id = %s", None, None, False)
        request_timings.on_commit(conn)
    request_timings.before_sql(conn, None, 'INSERT INTO "search_events" (user_id) VALUES (%s)', None, None, False)
    request_timings.after_sql(conn, None, 'INSERT INTO "search_events" (user_id) VALUES (%s)', None, None, False)
    response = request_timings.finish({"type": "product_search"}, timings, token, started)
    sql = response["meta"]["sql"]
    assert sql["count"] == 2 and sql["commits"] == 1
    assert sql["log"][0].startswith("session: SELECT conversation_sessions")
    assert sql["log"][1] == "session: COMMIT"
    assert sql["log"][2].startswith("other: INSERT search_events")
    assert "session" in response["meta"]["timings"]


def test_sql_outside_chat_request_is_ignored():
    conn = _FakeConn()
    request_timings.before_sql(conn, None, "SELECT 1", None, None, False)
    request_timings.after_sql(conn, None, "SELECT 1", None, None, False)       # скрипты / тесты — не падает
    request_timings.on_commit(conn)


def test_describe_sql():
    assert request_timings.describe_sql("UPDATE search_tasks SET x=1") == "UPDATE search_tasks"
    assert request_timings.describe_sql("WITH allowed AS (SELECT 1 FROM products p)") == "WITH products"
    assert request_timings.describe_sql("SELECT 1") == "SELECT"


def test_parts_inside_stage_are_not_counted_twice():
    # «search.embedding» — часть «search»: «other» не должен уйти в минус / потерять время
    timings, token, started = request_timings.start()
    with request_timings.stage("search"):
        with request_timings.stage("search.embedding"):
            time.sleep(0.03)
        time.sleep(0.03)
    response = request_timings.finish({"type": "product_search"}, timings, token, started)
    stages = response["meta"]["timings"]
    assert stages["search.embedding"] >= 30 and stages["search"] >= 60
    assert stages["total"] >= stages["search"]
    assert stages["other"] == stages["total"] - stages["search"]