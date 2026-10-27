"""
Нагрузочный замер чата (12.10). Отправляет N сообщений ОДНОВРЕМЕННО на запущенный сервер
и меряет, сколько ждал каждый «клиент».

Перед запуском — сервер в ОТДЕЛЬНОМ терминале, без LLM и смыслового поиска (меряем наш сервер и базу,
лимиты Gemini не тратим):
    PowerShell:
        $env:LLM_ENABLED="false"; $env:SEMANTIC_SEARCH_ENABLED="false"; uvicorn app.main:app
Потом этот скрипт: Run в PyCharm (корень проекта).

Пишет в базу служебные строки с user_id "load-test-*" (сессии, задачи, лог) — SQL уборки в конце вывода.
"""
import asyncio
import statistics
import time
import uuid

import httpx

URL = URL = "http://127.0.0.1:8001/chat/message"
LEVELS = [1, 10, 25, 50]          # сколько клиентов пишут одновременно
TIMEOUT_SECONDS = 120

# Разные запросы, как у живых клиентов (часть повторится — сработает кэш, это тоже реально)
QUERIES = [
    "nike 42", "adidas samba 40", "სარბენი ფეხსაცმელი 42", "ქალის ჯემპრი S", "crocs 42",
    "ბავშვის ბოტასი 30", "puma 41", "under armour shorts L", "მიტანა გაქვთ?", "ქალის ზამთრის ქურთუკი M",
    "reebok 43", "pegasus 42", "adidas hoodie M", "nike white 42", "გამარჯობა",
]


async def one_client(client: httpx.AsyncClient, run_id: str, index: int) -> tuple[float, str | None]:
    payload = {"user_id": f"load-test-{run_id}-{index}", "message": QUERIES[index % len(QUERIES)],
               "locale": "ka", "limit": 5, "offset": 0}
    started = time.perf_counter()
    try:
        response = await client.post(URL, json=payload)
        error = None if response.status_code == 200 else f"HTTP {response.status_code}"
    except Exception as exc:                      # таймаут, отказ соединения
        error = type(exc).__name__
    return time.perf_counter() - started, error


def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(share * (len(ordered) - 1))))]


async def run_level(concurrency: int) -> dict:
    run_id = uuid.uuid4().hex[:6]
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        started = time.perf_counter()
        results = await asyncio.gather(*[one_client(client, run_id, i) for i in range(concurrency)])
        wall = time.perf_counter() - started
    times = [t for t, error in results if error is None]
    errors = [error for _, error in results if error]
    return {
        "n": concurrency, "ok": len(times), "errors": len(errors),
        "error_kinds": sorted(set(errors)),
        "mean": statistics.mean(times) if times else 0,
        "p50": percentile(times, 0.50) if times else 0,
        "p95": percentile(times, 0.95) if times else 0,
        "max": max(times) if times else 0,
        "wall": wall, "rps": len(times) / wall if wall else 0,
    }


async def main():
    print(f"Сервер: {URL}\n")
    print(f"{'клиентов':>9} {'ок':>4} {'ошибок':>7} {'среднее':>9} {'p50':>7} {'p95':>7} {'макс':>7} {'всего':>7} {'ответов/с':>10}")
    print("-" * 78)
    for level in LEVELS:
        r = await run_level(level)
        print(f"{r['n']:>9} {r['ok']:>4} {r['errors']:>7} {r['mean']:>8.2f}с {r['p50']:>6.2f}с "
              f"{r['p95']:>6.2f}с {r['max']:>6.2f}с {r['wall']:>6.2f}с {r['rps']:>10.2f}"
              + (f"   ошибки: {', '.join(r['error_kinds'])}" if r["errors"] else ""))
        await asyncio.sleep(3)    # пауза, чтобы уровни не наложились
    print("\np50 — половина клиентов ждала не дольше; p95 — 95 из 100 клиентов ждали не дольше.")
    print("\nУборка служебных строк (Neon SQL Editor):")
    print("  DELETE FROM search_events WHERE user_id LIKE 'load-test-%';")
    print("  DELETE FROM search_tasks WHERE session_id IN "
          "(SELECT id FROM conversation_sessions WHERE user_id LIKE 'load-test-%');")
    print("  DELETE FROM conversation_sessions WHERE user_id LIKE 'load-test-%';")


if __name__ == "__main__":
    asyncio.run(main())