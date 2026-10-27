import time
from concurrent.futures import ThreadPoolExecutor

from app.services import cache_service


def test_get_does_not_raise_when_expired_key_accessed_concurrently():
    cache_service.clear()
    cache_service._cache_store["race-key"] = {
        "value": "old-value",
        "expires_at": time.time() - 1,  # уже просрочен
    }

    errors = []

    def worker():
        try:
            cache_service.get("race-key")
        except Exception as error:
            errors.append(error)

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(worker) for _ in range(200)]
        for future in futures:
            future.result()

    assert errors == []