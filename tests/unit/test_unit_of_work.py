"""19.10: Unit of Work — несколько изменений задачи = один COMMIT; ошибка → ROLLBACK (без «половины»)."""
from types import SimpleNamespace

import pytest

import app.repositories.conversation_repository as repository
import app.services.task_flow_service as task_flow
from app.db.unit_of_work import DEFER_COMMIT, save, single_commit
from app.schemas.task_transition import TaskTransition


class FakeDb:
    """Считает обращения вместо настоящей базы."""

    def __init__(self, fail_on_flush=False):
        self.info = {}
        self.added, self.commits, self.flushes, self.rollbacks = [], 0, 0, 0
        self.fail_on_flush = fail_on_flush

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flushes += 1
        if self.fail_on_flush:
            raise RuntimeError("Neon недоступен")

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_save_outside_unit_of_work_commits_as_before():
    db = FakeDb()
    save(db, "a")
    save(db, "b")
    assert db.commits == 2 and db.flushes == 0


def test_two_changes_inside_unit_of_work_one_commit():
    db = FakeDb()
    with single_commit(db):
        save(db, "cancel old")
        save(db, "create new")
        assert db.commits == 0              # пока внутри — ни одного COMMIT
    assert db.flushes == 2 and db.commits == 1
    assert DEFER_COMMIT not in db.info


def test_error_inside_unit_of_work_rolls_back():
    db = FakeDb(fail_on_flush=True)
    with pytest.raises(RuntimeError):
        with single_commit(db):
            save(db, "cancel old")
    assert db.commits == 0 and db.rollbacks == 1
    assert DEFER_COMMIT not in db.info      # следующий запрос снова коммитит как обычно


def test_restart_task_cancel_and_create_in_one_commit(monkeypatch):
    # как в живом замере 16.10: UPDATE (закрыть старую) + INSERT (новая) — было 2 COMMIT
    monkeypatch.setattr(repository, "get_active_search_tasks", lambda db, session: [])
    monkeypatch.setattr(task_flow, "should_create_followup_task", lambda result_mode: False)
    db = FakeDb()
    old_task = SimpleNamespace(status="active", current_step=None, completion_reason=None)

    new_task = task_flow.sync_search_task_after_result(
        db=db, session=SimpleNamespace(id=1), active_task=old_task, query="ქალის ფეხსაცმელი 36",
        result_mode="results", resolution_reason=TaskTransition.RESTART_TASK.value,
    )

    assert old_task.completion_reason == "restarted_by_user"
    assert new_task.query == "ქალის ფეხსაცმელი 36"
    assert db.flushes == 2 and db.commits == 1