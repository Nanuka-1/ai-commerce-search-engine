"""
15.10 (замер 3): настоящий конвейер чата (ChatUseCase.process_text) БЕЗ веб-сервера uvicorn.
Если здесь «понимание» ~1 с, а в виджете 5–10 с — время теряет сам сервер (uvicorn / --reload / async).
Если и здесь 5–10 с — ищем внутри нашего кода (что выполняется рядом с вызовом Gemini).
Пишет служебные строки чата под user_id 'perf-test-llm' (как measure_chat_timing.py). ~6 обращений к LLM.
Запуск из корня проекта: python check_chat_speed.py
"""
import time

from sqlalchemy import event, text

from app.db.session import SessionLocal, engine
from app.services import cache_service
from app.use_cases.chat_use_case import ChatUseCase

MESSAGES = [
    "კაცის სარბენი 42, 200 ლარამდე?",
    "ქალის ქურთუკი M ფასდაკლებით",
    "bichistvis fexsacmeli 35",
]
PAUSE_SECONDS = 4.5          # лимит free: 15 запросов в минуту

# 15.10 (замер 4): сколько SQL-запросов к Neon и сколько времени в них (как measure_chat_timing.py)
sql = {"count": 0, "ms": 0.0}


@event.listens_for(engine, "before_cursor_execute")
def _before(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start", []).append(time.perf_counter())


@event.listens_for(engine, "after_cursor_execute")
def _after(conn, cursor, statement, parameters, context, executemany):
    sql["count"] += 1
    sql["ms"] += (time.perf_counter() - conn.info["query_start"].pop()) * 1000


def main():
    use_case = ChatUseCase()
    db = SessionLocal()
    db.execute(text("SELECT 1"))          # прогрев соединения с Neon
    print(f"{'сообщение':<34}{'всего':>8}{'понимание':>11}{'текст ИИ':>10}{'SQL шт':>8}{'SQL мс':>8}"
          f"{'остальное':>11}  причина / ошибки")
    print("-" * 120)
    for index, message in enumerate(MESSAGES):
        if index:
            time.sleep(PAUSE_SECONDS)
        cache_service.clear()
        sql["count"], sql["ms"] = 0, 0.0
        started = time.perf_counter()
        response = use_case.process_text(db=db, user_id=f"perf-test-llm-{index}", message=message, locale="ka")
        total = round((time.perf_counter() - started) * 1000)
        meta = response.get("meta") or {}
        llm = (meta.get("understanding_ms") or 0) + (meta.get("ai_response_time_ms") or 0)
        rest = round(total - llm - sql["ms"])        # поиск в Python + эмбеддинг запроса (Gemini) + прочее
        print(f"{message[:33]:<34}{total:>8}{str(meta.get('understanding_ms')):>11}"
              f"{str(meta.get('ai_response_time_ms')):>10}{sql['count']:>8}{round(sql['ms']):>8}{rest:>11}"
              f"  {meta.get('ai_fallback_reason')} {meta.get('understanding_errors')}")
    db.close()
    print("\nУдалить тестовые строки (Neon SQL Editor):")
    print("  DELETE FROM search_events WHERE user_id LIKE 'perf-test-llm%';")
    print("  DELETE FROM search_tasks WHERE session_id IN "
          "(SELECT id FROM conversation_sessions WHERE user_id LIKE 'perf-test-llm%');")
    print("  DELETE FROM conversation_sessions WHERE user_id LIKE 'perf-test-llm%';")


if __name__ == "__main__":
    main()