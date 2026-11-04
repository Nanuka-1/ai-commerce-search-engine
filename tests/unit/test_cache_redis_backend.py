"""02.11: режим redis в cache_service — без настоящего Redis (клиент подменён)."""
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

from app.services import cache_service


class FakeRedis:
    def __init__(self, fail_with=None):
        self.data, self.calls, self.fail_with = {}, [], fail_with

    def _maybe_fail(self):
        if self.fail_with:
            raise self.fail_with("Redis недоступен")

    def get(self, key):
        self._maybe_fail()
        return self.data.get(key)

    def setex(self, key, ttl, value):
        self._maybe_fail()
        self.calls.append(("setex", key, ttl))
        self.data[key] = value

    def set(self, key, value):
        self._maybe_fail()
        self.calls.append(("set", key))
        self.data[key] = value


@pytest.fixture
def redis_backend(monkeypatch):
    def use(fake):
        monkeypatch.setattr(cache_service, "CACHE_BACKEND", "redis")
        monkeypatch.setattr(cache_service, "_get_redis_client", lambda: fake)
        return fake
    return use


def test_value_survives_round_trip_with_ttl(redis_backend):
    fake = redis_backend(FakeRedis())
    cache_service.set("chat:state:u1", {"size": "36", "gender": "women"}, ttl=1800)
    assert cache_service.get("chat:state:u1") == {"size": "36", "gender": "women"}
    assert fake.calls == [("setex", "chat:state:u1", 1800)]


def test_no_ttl_means_no_expiry_like_memory(redis_backend):
    fake = redis_backend(FakeRedis())
    cache_service.set("k", 1, ttl=None)
    cache_service.set("k2", 2, ttl=0)
    assert [call[0] for call in fake.calls] == ["set", "set"]


@pytest.mark.parametrize("error", [RedisConnectionError, RedisTimeoutError])
def test_redis_down_is_a_miss_not_a_crash(redis_backend, error):
    redis_backend(FakeRedis(fail_with=error))
    cache_service.set("chat:state:u1", {"size": "36"}, ttl=60)       # не падает
    assert cache_service.get("chat:state:u1") is None                # «ключа нет» → чат работает дальше


def test_tests_never_use_real_redis():
    # conftest.py ставит CACHE_BACKEND=memory: `doppler run -- pytest` не тронет настоящий Redis
    assert cache_service.CACHE_BACKEND == "memory"