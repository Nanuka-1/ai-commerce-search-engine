"""
15.10: время по этапам одного сообщения чата → meta.timings (наблюдаемость, «observability»).

  meta.timings = {"understanding": 0, "search": 5200, "ai_text": 2300, "other": 2600, "total": 10100}  (мс)
                 части с точкой («search.embedding») — внутри этапа «search», в total/other не суммируются
  meta.understanding_skipped = "timeout"   — если ИИ-понимание вызывали, но оно не дало результата
  meta.sql = {"count": 12, "ms": 3600, "log": ["session: SELECT conversation_sessions 290ms", ..., "COMMIT"]}
             — КАЖДОЕ обращение к базе за сообщение, с этапом: видно повторы и лишние походы

Этапы записываются через contextvars: у каждого запроса свой «блокнот», параллельные запросы не мешают друг другу.
Вне запроса чата (тесты, скрипты) ничего не записывается.
"""
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar

_current: ContextVar[dict | None] = ContextVar("chat_timings", default=None)
_stage: ContextVar[str | None] = ContextVar("chat_stage", default=None)
SKIPPED_KEY = "_understanding_skipped"
SQL_KEY = "_sql"
SQL_LOG_LIMIT = 60
TABLE = re.compile(r"\b(?:FROM|INTO|UPDATE)\s+\"?(\w+)", re.IGNORECASE)


def start():
    """Начать замер запроса. Возвращает (блокнот, токен, время старта) для finish()."""
    timings: dict = {}
    return timings, _current.set(timings), time.perf_counter()


def record(stage: str, started: float) -> None:
    """Добавить время этапа (мс) с момента started. Этап может встретиться несколько раз — суммируем."""
    timings = _current.get()
    if timings is not None:
        timings[stage] = timings.get(stage, 0) + round((time.perf_counter() - started) * 1000)


@contextmanager
def stage(name: str):
    """with request_timings.stage("session"): ... — время этапа + все SQL внутри подписаны этим этапом."""
    token = _stage.set(name)
    started = time.perf_counter()
    try:
        yield
    finally:
        _stage.reset(token)
        record(name, started)


def note_skipped(errors: list[str] | None) -> None:
    """ИИ-понимание вызывали, но результата нет: timeout / первая ошибка / no_result."""
    timings = _current.get()
    if timings is None:
        return
    errors = errors or []
    timings[SKIPPED_KEY] = "timeout" if "timeout" in errors else (str(errors[0])[:80] if errors else "no_result")


# --- счётчик обращений к базе (SQLAlchemy events) ---

def describe_sql(statement: str) -> str:
    """«SELECT conversation_sessions», «INSERT search_events», «WITH products»…"""
    words = (statement or "").split(None, 1)
    operation = words[0].upper() if words else "?"
    match = TABLE.search(statement or "")
    return f"{operation} {match.group(1)}" if match else operation


def _note_sql(text: str, ms: float | None) -> None:
    timings = _current.get()
    if timings is None:
        return
    log = timings.setdefault(SQL_KEY, [])
    log.append((f"{_stage.get() or 'other'}: {text}", ms))


def before_sql(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("chat_sql_start", []).append(time.perf_counter())


def after_sql(conn, cursor, statement, parameters, context, executemany):
    started = conn.info.get("chat_sql_start", [None]).pop() if conn.info.get("chat_sql_start") else None
    ms = round((time.perf_counter() - started) * 1000) if started else None
    _note_sql(describe_sql(statement), ms)


def on_commit(conn):
    _note_sql("COMMIT", None)       # время COMMIT событие не даёт, но число COMMIT'ов видно


def count_sql(engine) -> None:
    """Подключить счётчик к движку базы (один раз)."""
    if getattr(engine, "_chat_sql_counter", False):
        return
    from sqlalchemy import event
    event.listen(engine, "before_cursor_execute", before_sql)
    event.listen(engine, "after_cursor_execute", after_sql)
    event.listen(engine, "commit", on_commit)
    engine._chat_sql_counter = True


def finish(response, timings: dict, token, started: float):
    """Закончить замер: total, other (всё, что не попало в этапы) → response.meta; SQL-журнал → meta.sql."""
    _current.reset(token)
    if not isinstance(response, dict):
        return response
    skipped = timings.pop(SKIPPED_KEY, None)
    sql_log = timings.pop(SQL_KEY, [])
    total = round((time.perf_counter() - started) * 1000)
    # «search.embedding», «search.semantic» — части ВНУТРИ «search»: в «other» второй раз не вычитаем
    timings["other"] = max(0, total - sum(value for stage, value in timings.items() if "." not in stage))
    timings["total"] = total
    meta = {**(response.get("meta") or {}), "timings": timings}
    if skipped:
        meta["understanding_skipped"] = skipped
    if sql_log:
        meta["sql"] = {
            "count": sum(1 for text, _ in sql_log if not text.endswith("COMMIT")),
            "commits": sum(1 for text, _ in sql_log if text.endswith("COMMIT")),
            "ms": sum(ms or 0 for _, ms in sql_log),
            "log": [f"{text} {ms}ms" if ms is not None else text for text, ms in sql_log][:SQL_LOG_LIMIT],
        }
    response["meta"] = meta
    return response