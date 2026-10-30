"""
Клиент смыслового поиска (embeddings) через Gemini API.

Один модуль на весь проект: и загрузка каталога, и (позже) запросы клиентов.
Провайдер/модель/размерность — здесь, чтобы сменить их в одном месте.
Ключ — только из .env (GEMINI_API_KEY), в код не пишется.
"""
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from app.services import cache_service, request_timings

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768            # сжатая точка: в 4 раза меньше 3072, точность почти та же
RATE_LIMIT_WAIT_SECONDS = 60   # пауза при 429 (минутный лимит / перегрузка бесплатного уровня)
MAX_RETRIES = 5
QUERY_CACHE_TTL = 30 * 24 * 3600   # 15.10: точка запроса не зависит от каталога — храним 30 дней


class DailyQuotaExceeded(RuntimeError):
    """Дневной лимит Gemini исчерпан — ждать бессмысленно, сброс через часы."""


def is_daily_quota_error(error: Exception) -> bool:
    # В ответе Gemini: quotaId '...RequestsPerDayPerUser...' (07.10). Минутный лимит — PerMinute.
    return "429" in str(error) and "PerDay" in str(error)

_client = None
# 29.10: живьём — «Cannot send a request, as the client has been closed». Первый запрос после запуска сервера —
# фото: два потока (описание фото + метка фото) одновременно создали ДВА клиента; лишний, без ссылок,
# сборщик мусора закрыл прямо во время запроса. Замок: клиент создаётся ровно один раз.
_client_lock = threading.Lock()


def _get_client():
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:               # второй поток, дождавшись замка, берёт уже созданный
                from google import genai  # импорт здесь: тесты и код без ключа не требуют библиотеку
                load_dotenv()
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    raise RuntimeError("GEMINI_API_KEY не найден в .env")
                _client = genai.Client(api_key=api_key)
    return _client


def normalize(vector: list[float]) -> list[float]:
    """Длина вектора = 1. Для сжатой (768) точки Gemini это нужно делать самим;
    тогда косинусное сходство считается корректно."""
    length = math.sqrt(sum(x * x for x in vector))
    if length == 0:
        return list(vector)
    return [x / length for x in vector]


def _embed(texts: list[str], task_type: str, max_retries: int = MAX_RETRIES) -> list[list[float]]:
    from google.genai import types

    for attempt in range(max_retries):
        try:
            result = _get_client().models.embed_content(
                model=EMBEDDING_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBEDDING_DIM),
            )
            return [normalize(e.values) for e in result.embeddings]
        except Exception as error:
            if is_daily_quota_error(error):
                raise DailyQuotaExceeded("Дневной лимит Gemini исчерпан") from error
            if "429" not in str(error) or attempt == max_retries - 1:
                raise
            print(f"  лимит Gemini (429), жду {RATE_LIMIT_WAIT_SECONDS} с… попытка {attempt + 1}")
            time.sleep(RATE_LIMIT_WAIT_SECONDS)
    return []


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Точки для товаров (каталог)."""
    return _embed(texts, "RETRIEVAL_DOCUMENT")


def query_cache_key(text: str) -> str:
    # «Nike  42» и «nike 42» — один ключ; модель и размерность в ключе: сменили модель → старые точки не берём
    normalized = " ".join((text or "").lower().split())
    return f"emb:query:{EMBEDDING_MODEL}:{EMBEDDING_DIM}:{normalized}"


# 16.10: вектор запроса считаем В ФОНЕ, пока идёт точный поиск (они не зависят друг от друга).
# «В полёте»: если embed_query спросит тот же текст, пока фоновый вызов идёт, — ждём его, а не зовём Gemini второй раз.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="embed-prefetch")
_in_flight = {}
_in_flight_lock = threading.Lock()


def _embed_and_cache(text: str, key: str) -> list[float]:
    try:
        vector = _embed([text], "RETRIEVAL_QUERY", max_retries=1)[0]
        cache_service.set(key, vector, ttl=QUERY_CACHE_TTL)
        return vector
    finally:
        with _in_flight_lock:
            _in_flight.pop(key, None)


def prefetch_query(text: str) -> None:
    """Начать считать вектор запроса в фоне (если его ещё нет в кэше и он ещё не считается)."""
    key = query_cache_key(text)
    if cache_service.get(key):
        return
    with _in_flight_lock:
        if key not in _in_flight:
            _in_flight[key] = _executor.submit(_embed_and_cache, text, key)


def embed_query(text: str) -> list[float]:
    """Точка для запроса клиента. Без ожидания при 429: клиент не должен ждать минуту —
    гибрид сразу откатится на точный поиск. 16.10: повтор — из кэша; уже считается в фоне — ждём его."""
    key = query_cache_key(text)
    cached = cache_service.get(key)
    if cached:
        return cached
    with _in_flight_lock:
        future = _in_flight.get(key)
    with request_timings.stage("search.embedding"):          # замер — сколько ЖДАЛИ вектор
        if future is not None:
            return future.result()
        vector = _embed([text], "RETRIEVAL_QUERY", max_retries=1)[0]
    cache_service.set(key, vector, ttl=QUERY_CACHE_TTL)
    return vector