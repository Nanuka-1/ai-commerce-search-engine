"""
Нагрузочный замер чата. Отправляет N сообщений ОДНОВРЕМЕННО и меряет, сколько ждал каждый «клиент».

12.10 — первая версия (локальный сервер).
06.11 — замер на Vercel (прод): адрес и уровни из командной строки + отдельный «прогрев»
        (первый запрос после паузы будит Vercel — «холодный старт», его меряем отдельно).

Запуск из корня проекта (секреты НЕ нужны — скрипт только шлёт запросы на сайт):
    python load_test.py                                   # прод, уровни 1 10 25 50 100
    python load_test.py https://ai-commerce-search-engine.vercel.app 5 10
    python load_test.py http://127.0.0.1:8001 1 10        # локальный сервер

Пишет в базу служебные строки с user_id "load-test-*" (сессии, задачи, лог) — SQL уборки в конце вывода.
"""
import asyncio
import statistics
import sys
import time
import uuid

import httpx

DEFAULT_BASE_URL = "https://ai-commerce-search-engine.vercel.app"
DEFAULT_LEVELS = [1, 10, 25, 50, 100]   # сколько клиентов пишут одновременно
TIMEOUT_SECONDS = 120
PAUSE_BETWEEN_LEVELS = 5                # секунд, чтобы уровни не наложились

# Разные запросы, как у живых клиентов (часть повторится — сработает кэш, это тоже реально)
QUERIES = [
    "nike 42", "adidas samba 40", "სარბენი ფეხსაცმელი 42", "ქალის ჯემპრი S", "crocs 42",
    "ბავშვის ბოტასი 30", "puma 41", "under armour shorts L", "მიტანა გაქვთ?", "ქალის ზამთრის ქურთუკი M",
    "reebok 43", "pegasus 42", "adidas hoodie M", "nike white 42", "გამარჯობა",
]


def parse_args(argv: list[str]) -> tuple[str, list[int]]:
    base_url = DEFAULT_BASE_URL
    levels = DEFAULT_LEVELS
    args = list(argv)
    if args and not args[0].isdigit():
        base_url = args.pop(0)
    if args:
        levels = [int(value) for value in args]
    return base_url.rstrip("/"), levels


async def one_client(client: httpx.AsyncClient, url: str, run_id: str, index: int) -> tuple[float, str | None]:
    payload = {"user_id": f"load-test-{run_id}-{index}", "message": QUERIES[index % len(QUERIES)],
               "locale": "ka", "limit": 5, "offset": 0}
    started = time.perf_counter()
    try:
        response = await client.post(url, json=payload)
        error = None if response.status_code == 200 else f"HTTP {response.status_code}"
    except Exception as exc:                      # таймаут, отказ соединения
        error = type(exc).__name__
    return time.perf_counter() - started, error


def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(share * (len(ordered) - 1))))]


async def run_level(client: httpx.AsyncClient, url: str, concurrency: int) -> dict:
    run_id = uuid.uuid4().hex[:6]
    started = time.perf_counter()
    results = await asyncio.gather(*[one_client(client, url, run_id, i) for i in range(concurrency)])
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
    base_url, levels = parse_args(sys.argv[1:])
    url = f"{base_url}/chat/message"
    print(f"Сервер: {url}\nУровни: {levels}\n")

    # Лимит соединений больше самого большого уровня — иначе ждал бы наш скрипт, а не сервер.
    limits = httpx.Limits(max_connections=max(levels) + 10, max_keepalive_connections=max(levels) + 10)
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, limits=limits) as client:
        # Прогрев: будим сервер (холодный старт Vercel) — в таблицу уровней не входит.
        warm_time, warm_error = await one_client(client, url, "warmup", 0)
        print(f"Прогрев (1 запрос, может включать холодный старт): {warm_time:.2f}с"
              + (f"  ОШИБКА: {warm_error}" if warm_error else "") + "\n")

        print(f"{'клиентов':>9} {'ок':>4} {'ошибок':>7} {'среднее':>9} {'p50':>7} {'p95':>7} {'макс':>7} "
              f"{'всего':>7} {'ответов/с':>10}")
        print("-" * 78)
        for level in levels:
            r = await run_level(client, url, level)
            print(f"{r['n']:>9} {r['ok']:>4} {r['errors']:>7} {r['mean']:>8.2f}с {r['p50']:>6.2f}с "
                  f"{r['p95']:>6.2f}с {r['max']:>6.2f}с {r['wall']:>6.2f}с {r['rps']:>10.2f}"
                  + (f"   ошибки: {', '.join(r['error_kinds'])}" if r["errors"] else ""))
            await asyncio.sleep(PAUSE_BETWEEN_LEVELS)

    print("\np50 — половина клиентов ждала не дольше; p95 — 95 из 100 клиентов ждали не дольше.")
    print("Время включает дорогу Грузия → сервер в США и обратно (~0.2–0.3 с).")
    print("\nУборка служебных строк (Neon SQL Editor):")
    print("  DELETE FROM search_events WHERE user_id LIKE 'load-test-%';")
    print("  DELETE FROM search_tasks WHERE session_id IN "
          "(SELECT id FROM conversation_sessions WHERE user_id LIKE 'load-test-%');")
    print("  DELETE FROM conversation_sessions WHERE user_id LIKE 'load-test-%';")


if __name__ == "__main__":
    asyncio.run(main())