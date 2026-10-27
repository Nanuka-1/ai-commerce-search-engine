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

_cache_store = {}
_redis_client = None


def _get_redis_client():
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    import redis

    _redis_client = redis.from_url(REDIS_URL)
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
        except (UnpicklingError, EOFError, AttributeError, TypeError) as error:
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


def set(key: str, value, ttl: int = 60):
    if CACHE_BACKEND == "redis":
        from redis.exceptions import RedisError

        client = _get_redis_client()

        try:
            client.setex(key, ttl, pickle.dumps(value))
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