"""
Кэш: memory (одна программа, по умолчанию) или redis (общая память для всех копий программы — Vercel, сервер).

02.11 (подготовка к Vercel + Upstash Redis):
- Предел ожидания Redis 1 с (`REDIS_TIMEOUT_SECONDS`): Redis недоступен → кэш «промахнулся», чат работает дальше,
  а не висит до таймаута Vercel (раньше ожидание не было ограничено).
- `ttl=None` / 0 = без срока, как в memory (раньше в redis `setex` с 0 падал).
- Ошибка подключения / ответа Redis → предупреждение в лог и поведение «как будто ключа нет» (как раньше).

03.11: «номер дня» каталога (версионирование кэша поиска):
- `catalog:version` — номер, который скрипты (скрапер, новинки, векторы) меняют в конце работы
  (`bump_catalog_version`). Ключи поиска содержат номер: `search:v<номер>:…` → после обновления каталога
  старые записи никто не читает, через сутки они сами исчезают. Разговоры (`chat:*`) и ИИ не трогаются.
- Срок кэша поиска (`search_cache_ttl`): redis — сутки (номер общий для всех программ и скриптов);
  memory — 60 с, как раньше (у скрипта и у сервера своя память, номер между ними не передаётся).
"""
import logging
import os
import pickle
from pickle import UnpicklingError
import time

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

CACHE_BACKEND = os.getenv("CACHE_BACKEND", "memory")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_TIMEOUT_SECONDS = float(os.getenv("REDIS_TIMEOUT_SECONDS", "1"))

_cache_store = {}
_redis_client = None

CATALOG_VERSION_KEY = "catalog:version"
SEARCH_CACHE_TTL_REDIS = 24 * 3600   # сутки: каталог меняется раз в день (скрапер), смена номера — сразу свежие данные
SEARCH_CACHE_TTL_MEMORY = 60         # память одной программы: номер дня от скрипта сюда не доходит — коротко, как раньше


def _get_redis_client():
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    import redis

    _redis_client = redis.from_url(
        REDIS_URL,
        socket_connect_timeout=REDIS_TIMEOUT_SECONDS,   # подключение
        socket_timeout=REDIS_TIMEOUT_SECONDS,           # каждый ответ
        health_check_interval=30,                       # проверить соединение, если простаивало (Vercel «замирает»)
    )
    return _redis_client


def get(key: str):
    if CACHE_BACKEND == "redis":
        from redis.exceptions import RedisError

        client = _get_redis_client()

        try:
            raw_value = client.get(key)
        except RedisError as error:
            logger.warning(
                "Cache get failed",
                extra={
                    "cache_key": key,
                    "backend": CACHE_BACKEND,
                    "error": str(error),
                },
            )
            return None

        if raw_value is None:
            logger.info(
                "Cache miss",
                extra={
                    "cache_key": key,
                    "backend": CACHE_BACKEND,
                },
            )
            return None

        try:
            value = pickle.loads(raw_value)
        except (UnpicklingError, EOFError, AttributeError, TypeError, ImportError) as error:
            # ImportError / AttributeError: после выкладки новой версии старая запись ссылается на изменённый класс
            logger.warning(
                "Cache deserialize failed",
                extra={
                    "cache_key": key,
                    "backend": CACHE_BACKEND,
                    "error": str(error),
                },
            )
            return None

        logger.info(
            "Cache hit",
            extra={
                "cache_key": key,
                "backend": CACHE_BACKEND,
            },
        )

        return value

    item = _cache_store.get(key)

    if not item:
        logger.info(
            "Cache miss",
            extra={
                "cache_key": key,
                "backend": CACHE_BACKEND,
            },
        )
        return None

    value = item["value"]
    expires_at = item["expires_at"]

    if expires_at is not None and time.time() > expires_at:
        _cache_store.pop(key, None)

        logger.info(
            "Cache expired",
            extra={
                "cache_key": key,
                "backend": CACHE_BACKEND,
            },
        )

        return None

    logger.info(
        "Cache hit",
        extra={
            "cache_key": key,
            "backend": CACHE_BACKEND,
        },
    )

    return value


def set(key: str, value, ttl: int | None = 60):
    if CACHE_BACKEND == "redis":
        from redis.exceptions import RedisError

        client = _get_redis_client()

        try:
            data = pickle.dumps(value)
            if ttl:
                client.setex(key, int(ttl), data)
            else:
                client.set(key, data)            # без срока — как в memory
        except RedisError as error:
            logger.warning(
                "Cache set failed",
                extra={
                    "cache_key": key,
                    "backend": CACHE_BACKEND,
                    "ttl": ttl,
                    "error": str(error),
                },
            )
            return

        logger.info(
            "Cache set",
            extra={
                "cache_key": key,
                "backend": CACHE_BACKEND,
                "ttl": ttl,
            },
        )
        return

    expires_at = time.time() + ttl if ttl else None

    _cache_store[key] = {
        "value": value,
        "expires_at": expires_at,
    }

    logger.info(
        "Cache set",
        extra={
            "cache_key": key,
            "backend": CACHE_BACKEND,
            "ttl": ttl,
        },
    )


def delete(key: str):
    if CACHE_BACKEND == "redis":
        from redis.exceptions import RedisError

        client = _get_redis_client()

        try:
            client.delete(key)
        except RedisError as error:
            logger.warning(
                "Cache delete failed",
                extra={
                    "cache_key": key,
                    "backend": CACHE_BACKEND,
                    "error": str(error),
                },
            )
            return

        logger.info(
            "Cache deleted",
            extra={
                "cache_key": key,
                "backend": CACHE_BACKEND,
            },
        )
        return

    _cache_store.pop(key, None)

    logger.info(
        "Cache deleted",
        extra={
            "cache_key": key,
            "backend": CACHE_BACKEND,
        },
    )


def clear():
    """Очистить ВЕСЬ кэш. Внимание: в redis — вся база Redis (и разговоры клиентов тоже)."""
    if CACHE_BACKEND == "redis":
        from redis.exceptions import RedisError

        client = _get_redis_client()

        try:
            client.flushdb()
        except RedisError as error:
            logger.warning(
                "Cache clear failed",
                extra={
                    "backend": CACHE_BACKEND,
                    "error": str(error),
                },
            )
            return

        logger.info(
            "Cache cleared",
            extra={
                "backend": CACHE_BACKEND,
            },
        )
        return

    _cache_store.clear()

    logger.info(
        "Cache cleared",
        extra={
            "backend": CACHE_BACKEND,
        },
    )


def catalog_version() -> str:
    """Текущий «номер дня» каталога. Нет записи / Redis недоступен → "0" (поиск всё равно работает)."""
    value = get(CATALOG_VERSION_KEY)
    return str(value) if value is not None else "0"


def bump_catalog_version() -> str:
    """Каталог изменился (конец скрапера / новинок / векторов, новый товар) → новый номер.
    Номер — время в наносекундах: всегда новый, без «прочитать-прибавить-записать»."""
    version = str(time.time_ns())
    set(CATALOG_VERSION_KEY, version, ttl=None)    # без срока: номер живёт, пока его не сменят
    logger.info("Catalog version bumped", extra={"backend": CACHE_BACKEND, "version": version})
    return version


def search_cache_ttl() -> int:
    """Срок записей поиска: сутки в redis, 60 с в памяти."""
    return SEARCH_CACHE_TTL_REDIS if CACHE_BACKEND == "redis" else SEARCH_CACHE_TTL_MEMORY