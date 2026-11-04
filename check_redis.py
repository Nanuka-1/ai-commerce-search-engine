"""
02.11: проверка Upstash Redis через НАШ cache_service (запись → чтение → срок → удаление) + время одной команды.
Запуск из корня проекта:  doppler run -- python check_redis.py
Адрес берётся из REDIS_URL (Doppler) и на экран не выводится. Режим redis включается только внутри скрипта —
локальный чат и тесты остаются на памяти.
"""
import os
import time

os.environ["CACHE_BACKEND"] = "redis"            # до импорта cache_service

from app.services import cache_service           # noqa: E402

url = os.environ.get("REDIS_URL", "")
print("REDIS_URL задан:", bool(url), "| TLS (rediss://):", url.startswith("rediss://"))

key = "check:redis:hello"
started = time.perf_counter()
cache_service.set(key, {"size": "36", "gender": "women"}, ttl=60)
set_ms = (time.perf_counter() - started) * 1000

started = time.perf_counter()
value = cache_service.get(key)
get_ms = (time.perf_counter() - started) * 1000

ttl_left = cache_service._get_redis_client().ttl(key)
cache_service.delete(key)
after_delete = cache_service.get(key)

print(f"записали и прочитали: {value}")
print(f"срок у ключа: {ttl_left} с (ждём ≈ 60)")
print(f"после удаления: {after_delete} (ждём None)")
print(f"время: запись {set_ms:.0f} мс, чтение {get_ms:.0f} мс (из Тбилиси до США — сотни мс; на Vercel рядом — единицы)")
print("✅ Redis работает" if value == {"size": "36", "gender": "women"} and after_delete is None
      else "❌ что-то не так — пришлите вывод")