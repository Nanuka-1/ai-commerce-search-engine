"""15.10: меньше походов в базу за одно сообщение (Neon далеко: ~300 мс на каждый).
- объекты не «забываются» после COMMIT (expire_on_commit=False) → нет повторных SELECT;
- новая задача: активные задачи ищем ОДИН раз (раньше — в сервисе и ещё раз в репозитории), без перечитывания."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.session import SessionLocal
from app.services import conversation_service


def test_objects_are_not_forgotten_after_commit():
    assert SessionLocal.kw["expire_on_commit"] is False


def _db_with_sql_log():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    statements = []

    def remember(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip())

    event.listen(engine, "before_cursor_execute", remember)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)(), statements


def test_new_task_reads_active_tasks_once_without_refresh():
    db, statements = _db_with_sql_log()
    session = conversation_service.get_or_create_session(db, "u-round-trips")
    statements.clear()

    task = conversation_service.create_search_task(db, session, query="nike 42")

    selects = [s for s in statements if s.upper().startswith("SELECT")]
    assert len(selects) == 1                     # только «есть ли активные задачи» — один раз, без перечитывания
    assert task.id is not None and task.query == "nike 42"