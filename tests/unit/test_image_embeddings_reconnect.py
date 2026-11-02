"""02.11: обрыв соединения с Neon при сохранении точек → один повтор, готовые точки не теряются."""
import pytest
from sqlalchemy.exc import OperationalError

from ingestion.build_image_embeddings import save_rows


class FakeDb:
    def __init__(self, failures):
        self.failures, self.calls = failures, []

    def execute(self, sql, rows):
        self.calls.append("execute")
        if self.failures:
            self.failures -= 1
            raise OperationalError("INSERT", {}, Exception("server closed the connection unexpectedly"))

    def commit(self):
        self.calls.append("commit")

    def rollback(self):
        self.calls.append("rollback")


def test_connection_drop_is_retried_once_and_rows_saved():
    db = FakeDb(failures=1)
    save_rows(db, [{"page_url": "p1"}])
    assert db.calls == ["execute", "rollback", "execute", "commit"]


def test_second_drop_is_raised():
    with pytest.raises(OperationalError):
        save_rows(FakeDb(failures=2), [{"page_url": "p1"}])


def test_normal_save_unchanged():
    db = FakeDb(failures=0)
    save_rows(db, [{"page_url": "p1"}])
    assert db.calls == ["execute", "commit"]