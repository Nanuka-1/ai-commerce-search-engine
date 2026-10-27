"""
Замер чата: сколько SQL-запросов к Neon и сколько времени уходит на одно сообщение.

Вызывает настоящий конвейер чата (ChatUseCase.process_text) — тот же, что использует API.
Кэш очищается перед каждым сообщением, чтобы мерить реальную работу с базой.

Пишет только служебные строки чата (сессия, задача поиска, событие поиска)
под user_id 'perf-test-...'. Таблицу products НЕ меняет.
Удалить тестовые строки после замера — SQL в конце вывода.
"""
import re
import time
from collections import Counter

from sqlalchemy import event, text

from app.db.session import SessionLocal, engine
from app.services import cache_service
from app.use_cases.chat_use_case import ChatUseCase

TEST_MESSAGES = [
    "nike 42",
    "nike 42.5",
    "adidas hoodie M",
    "nike air max 90 42",
    "pegasus",
    "puma black 41",
    "crocs 42",
    "under armour shorts L",
    "მამაკაცის სპორტული ფეხსაცმელი 43",
    "ქალის ჯემპრი S",
    "CW2288-111",
    "hello",
]

TABLE_PATTERN = re.compile(r"\b(?:FROM|INTO|UPDATE)\s+\"?(\w+)", re.IGNORECASE)

current = {"count": 0, "sql_time": 0.0, "tables": Counter()}


@event.listens_for(engine, "before_cursor_execute")
def _before(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start", []).append(time.perf_counter())


@event.listens_for(engine, "after_cursor_execute")
def _after(conn, cursor, statement, parameters, context, executemany):
    elapsed = time.perf_counter() - conn.info["query_start"].pop()
    current["count"] += 1
    current["sql_time"] += elapsed
    match = TABLE_PATTERN.search(statement)
    current["tables"][match.group(1) if match else "other"] += 1


def reset_counters():
    current["count"] = 0
    current["sql_time"] = 0.0
    current["tables"] = Counter()


def main():
    use_case = ChatUseCase()
    db = SessionLocal()

    db.execute(text("SELECT 1"))  # прогрев соединения, чтобы не мерить подключение к Neon
    print(f"{'сообщение':<36}{'всего, мс':>10}{'SQL шт':>8}{'SQL, мс':>9}  тип / режим  | запросы по таблицам")
    print("-" * 120)

    totals = []
    for index, message in enumerate(TEST_MESSAGES):
        cache_service.clear()
        reset_counters()

        started = time.perf_counter()
        response = use_case.process_text(
            db=db,
            user_id=f"perf-test-{index}",
            message=message,
            locale="ka",
        )
        total_ms = (time.perf_counter() - started) * 1000

        response_type = response.get("type")
        mode = (response.get("data") or {}).get("results", {}).get("search_strategy") if isinstance(response.get("data"), dict) else None
        tables = ", ".join(f"{table}:{count}" for table, count in current["tables"].most_common())

        print(
            f"{message[:35]:<36}{total_ms:>10.0f}{current['count']:>8}{current['sql_time'] * 1000:>9.0f}"
            f"  {response_type} / {mode}  | {tables}"
        )
        totals.append((total_ms, current["count"], current["sql_time"] * 1000))

    db.close()

    n = len(totals)
    avg_total = sum(t[0] for t in totals) / n
    avg_count = sum(t[1] for t in totals) / n
    avg_sql = sum(t[2] for t in totals) / n
    print("-" * 120)
    print(f"Среднее на сообщение: всего {avg_total:.0f} мс, SQL-запросов {avg_count:.1f}, "
          f"время в БД {avg_sql:.0f} мс ({avg_sql / avg_total * 100:.0f}% от ответа)")
    print("\nУдалить тестовые строки после замера (Neon SQL Editor):")
    print("  DELETE FROM search_events WHERE user_id LIKE 'perf-test-%';")
    print("  DELETE FROM search_tasks WHERE session_id IN "
          "(SELECT id FROM conversation_sessions WHERE user_id LIKE 'perf-test-%');")
    print("  DELETE FROM conversation_sessions WHERE user_id LIKE 'perf-test-%';")


if __name__ == "__main__":
    main()