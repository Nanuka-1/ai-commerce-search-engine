import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10,
    )
    # 02.11: схему Postgres (Neon / сервер) ведёт ТОЛЬКО Alembic: `doppler run -- alembic upgrade head`.
    # create_all здесь больше не зовём — иначе два «хозяина» схемы (create_all не добавляет индексы
    # к существующей таблице → так потерялся ix_products_product_type, см. миграцию 0002).
else:
    DB_PATH = BASE_DIR / "store.db"
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)   # запасная локальная SQLite без DATABASE_URL — как раньше

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # 15.10: после COMMIT не «забывать» объекты → нет лишних SELECT к Neon
    bind=engine
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()