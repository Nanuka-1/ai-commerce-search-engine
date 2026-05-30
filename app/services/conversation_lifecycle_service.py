from datetime import UTC, datetime, timedelta

from app.db.models import SearchTask


TASK_TIMEOUT_MINUTES = 15


def normalize_datetime_to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def is_task_expired(
    task: SearchTask,
    timeout_minutes: int = TASK_TIMEOUT_MINUTES,
) -> bool:
    if task.updated_at is None:
        return False

    updated_at = normalize_datetime_to_utc(task.updated_at)
    expires_at = updated_at + timedelta(minutes=timeout_minutes)
    now = datetime.now(UTC)


    return expires_at < now