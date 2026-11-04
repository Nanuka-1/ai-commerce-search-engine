from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.api.analytics import router as analytics_router
from app.api.chat import router as chat_router
from app.api.products import router as products_router
from app.api.promo import router as promo_router
from app.db.session import engine
from app.services import cache_service

app = FastAPI()

# 04.11: create_all здесь убран — схему Postgres ведёт только Alembic (02.11 убрали и из session.py;
# здесь осталась вторая копия: на Vercel при каждом холодном старте лишние запросы к Neon и второй «хозяин» схемы).
# Запасная локальная SQLite без DATABASE_URL по-прежнему создаётся в session.py.


@app.get("/health")
def health():
    """Жив ли сам сервер (без базы) — дёшево, для частых проверок."""
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready():
    """04.11: готов ли сервер отвечать клиентам — база отвечает, Redis (если включён) отвечает.
    CD после выкладки стучится сюда: 200 — всё хорошо, 503 — откат. Секретов в ответе нет."""
    checks = {}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as error:
        checks["database"] = f"error: {type(error).__name__}"
    if cache_service.CACHE_BACKEND == "redis":
        try:
            cache_service._get_redis_client().ping()
            checks["redis"] = "ok"
        except Exception as error:
            checks["redis"] = f"error: {type(error).__name__}"
    ready = all(value == "ok" for value in checks.values())
    return JSONResponse({"status": "ok" if ready else "error", "checks": checks},
                        status_code=200 if ready else 503)


@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


app.include_router(products_router)
app.include_router(chat_router)
app.include_router(analytics_router)
app.include_router(promo_router)      # бегущая строка: GET /promo/ticker (настройки — app/config/promo.json)

# Демо-страница чата: http://localhost:8000/demo/ (прототип; позже — сборка React из frontend/)
app.mount("/demo", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="demo")