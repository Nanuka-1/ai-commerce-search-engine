"""
16.10 (этап 1, п.2): запись аналитики поиска (search_events) ПОСЛЕ ответа — клиент её не ждёт (−0.4–0.8 с).

  ответ клиенту ← сразу
  запись события → в фоне, СВОЯ сессия базы (сессию запроса FastAPI закрывает после ответа)

Безопасность:
  - В фон уходят только простые значения (sku первого товара, число результатов, стратегия), не объекты базы.
  - Ошибка записи не роняет чат — только предупреждение в лог (аналитика не важнее ответа клиенту).
  - Тесты и скрипты, у которых своя база (не основной движок приложения), пишут как раньше — сразу и в ту же сессию.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="search-log")


def _app_database():
    from app.db.session import SessionLocal, engine
    return engine, SessionLocal


def _field(item, name):
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def _snapshot(kwargs: dict) -> dict:
    """Только простые значения — объекты базы нельзя трогать из другого потока после закрытия сессии."""
    snapshot = dict(kwargs)
    snapshot["items"] = [{"sku": _field(item, "sku")} for item in (kwargs.get("items") or [])]
    context = kwargs.get("search_context")
    if context is not None:
        snapshot["search_context"] = SimpleNamespace(
            search_strategy=getattr(context, "search_strategy", None),
            matched_by=getattr(context, "matched_by", None),
            fallback_level=getattr(context, "fallback_level", None),
        )
    if kwargs.get("ai_meta") is not None:
        snapshot["ai_meta"] = dict(kwargs["ai_meta"])
    return snapshot


def log_after_response(log_function, db, **kwargs):
    """Вызвать log_function(db=..., **kwargs): для основной базы приложения — в фоне со своей сессией,
    иначе (тесты, своя база) — сразу, как раньше."""
    engine, session_factory = _app_database()
    bind = db.get_bind() if db is not None and hasattr(db, "get_bind") else None
    if bind is None or bind is not engine:
        return log_function(db=db, **kwargs)

    snapshot = _snapshot(kwargs)

    def job():
        background_db = session_factory()
        try:
            log_function(db=background_db, **snapshot)
        except Exception as error:          # аналитика не должна ронять чат
            logger.warning("Background search event failed: %s", error)
        finally:
            background_db.close()

    _executor.submit(job)
    return None