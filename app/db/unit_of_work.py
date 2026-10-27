"""19.10: Unit of Work — несколько изменений в базе = ОДИН COMMIT («всё или ничего»).

Без него: «закрыть старую задачу» → COMMIT, «создать новую» → COMMIT. Сбой между ними → клиент без активной
задачи. С ним: внутри блока `single_commit(db)` репозитории делают только flush (SQL ушёл в базу, id появился,
но транзакция открыта), в конце блока — один COMMIT; ошибка → ROLLBACK (не остаётся «половины» изменений).
"""
from contextlib import contextmanager

DEFER_COMMIT = "defer_commit"      # метка в db.info (словарь SQLAlchemy Session для своих данных)


def _info(db):
    info = getattr(db, "info", None)
    return info if isinstance(info, dict) else None   # заглушка в тесте (MagicMock, None) — не настоящая сессия


@contextmanager
def single_commit(db):
    info = _info(db)
    if info is None or info.get(DEFER_COMMIT):
        yield                       # не настоящая сессия или уже внутри единицы работы — ничего не меняем
        return
    info[DEFER_COMMIT] = True
    try:
        yield
        info.pop(DEFER_COMMIT, None)
        db.commit()
    except Exception:
        info.pop(DEFER_COMMIT, None)
        db.rollback()
        raise


def save(db, obj=None) -> None:
    """Вместо `db.add(obj); db.commit()` в репозиториях. Вне single_commit — как раньше (сразу COMMIT)."""
    if obj is not None:
        db.add(obj)
    info = _info(db)
    if info is not None and info.get(DEFER_COMMIT):
        db.flush()
    else:
        db.commit()