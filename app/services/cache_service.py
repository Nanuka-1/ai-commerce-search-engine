import os
import pickle
import time

from dotenv import load_dotenv

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
        client = _get_redis_client()
        raw_value = client.get(key)

        if raw_value is None:
            return None

        return pickle.loads(raw_value)

    item = _cache_store.get(key)

    if not item:
        return None

    value = item["value"]
    expires_at = item["expires_at"]

    if expires_at is not None and time.time() > expires_at:
        del _cache_store[key]
        return None

    return value


def set(key: str, value, ttl: int = 60):
    if CACHE_BACKEND == "redis":
        client = _get_redis_client()
        client.setex(key, ttl, pickle.dumps(value))
        print("CACHE SET:", key)
        return

    expires_at = time.time() + ttl if ttl else None

    _cache_store[key] = {
        "value": value,
        "expires_at": expires_at,
    }

    print("CACHE SET:", key)


def delete(key: str):
    if CACHE_BACKEND == "redis":
        client = _get_redis_client()
        client.delete(key)
        return

    if key in _cache_store:
        del _cache_store[key]