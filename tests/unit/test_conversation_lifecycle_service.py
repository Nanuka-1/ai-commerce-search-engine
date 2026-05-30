from datetime import datetime, timedelta, UTC
from types import SimpleNamespace

from app.services.conversation_lifecycle_service import is_task_expired


def test_task_is_expired_after_15_minutes():
    task = SimpleNamespace(
        updated_at=datetime.now(UTC) - timedelta(minutes=16),
    )

    result = is_task_expired(task)

    assert result is True


def test_task_is_not_expired_before_15_minutes():
    task = SimpleNamespace(
        updated_at=datetime.now(UTC) - timedelta(minutes=14),
    )

    result = is_task_expired(task)

    assert result is False