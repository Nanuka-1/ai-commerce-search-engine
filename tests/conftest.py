from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.models import Base

import os

os.environ["LLM_ENABLED"] = "false"  # тесты никогда не зовут настоящий Gemini; LLM в тестах — только подменой


BASE_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = BASE_DIR / "test_store.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)


# Драйвер sqlite3 по умолчанию сам управляет транзакциями и ломает SAVEPOINT.
# Отдаём управление SQLAlchemy (официальный рецепт из документации SQLAlchemy),
# иначе откат теста и begin_nested() в коде скрапера работают некорректно.
@event.listens_for(test_engine, "connect")
def _disable_sqlite_autotransactions(dbapi_connection, connection_record):
    dbapi_connection.isolation_level = None


@event.listens_for(test_engine, "begin")
def _emit_begin(conn):
    conn.exec_driver_sql("BEGIN")


TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


@pytest.fixture(scope="session", autouse=True)
def prepare_test_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    yield

    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture
def db():
    # Каждый тест работает внутри своей транзакции, которая в конце откатывается.
    # db.commit() внутри теста превращается в SAVEPOINT — код ведёт себя как обычно,
    # но после теста база возвращается в исходное (пустое) состояние,
    # и тесты не видят данные друг друга.
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()