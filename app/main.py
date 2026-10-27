from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.analytics import router as analytics_router
from app.api.chat import router as chat_router
from app.api.products import router as products_router
from app.api.promo import router as promo_router
from app.db.models import Base
from app.db.session import engine

app = FastAPI()

Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}


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