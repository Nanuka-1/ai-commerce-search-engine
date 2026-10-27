import re

from app.db.models import SearchTask

from app.schemas.task_transition import TaskTransition

from app.services.intent_router import extract_size_from_query
from app.services.task_transition_service import (
    classify_task_transition,
)
from app.schemas.conversation_resolution import ConversationResolution


def refine_task_query(task_query: str, message: str) -> str:
    """09.10: уточнение дописывается к ТЕКСТУ старого запроса (раньше запрос пересобирался только из
    распознанных полей, и слова вроде "სარბენი ფეხსაცმელი" терялись: оставалось "43").
    Новый размер заменяет старый."""
    base = task_query
    new_size = extract_size_from_query(message)
    old_size = extract_size_from_query(task_query)
    if new_size and old_size:
        base = re.sub(rf"(?<!\S){re.escape(old_size)}(?!\S)", " ", base, flags=re.IGNORECASE)
    # 15.10: дописываем только НОВЫЕ слова — повтор того же сообщения не удваивает запрос
    # («ქალის ჯემპრი S» + «ქალის ჯემპრი S» было → «ქალის ჯემპრი ქალის ჯემპრი S»: другие карточки и промах кэша)
    seen = {word.lower() for word in base.split()}
    added = []
    for word in message.split():
        if word.lower() not in seen:
            seen.add(word.lower())
            added.append(word)
    return " ".join(f"{base} {' '.join(added)}".split())

def resolve_restart_task(message: str) -> ConversationResolution:
    return ConversationResolution(
        query=message,
        should_search=True,
        reason="restart_task",
    )


def resolve_duplicate_task(
    task: SearchTask,
    message: str,
) -> ConversationResolution:
    return ConversationResolution(
        query=task.query or message,
        should_search=False,
        reason="duplicate",
    )

def resolve_message_from_active_task(
    task: SearchTask | None,
    message: str,
) -> ConversationResolution:


    if task is None:
        return ConversationResolution(
            query=message,
            should_search=True,
            reason="new_message",
        )

    transition_type = classify_task_transition(task, message)



    if transition_type == TaskTransition.RESTART_TASK.value:
        return resolve_restart_task(message)

    if transition_type == TaskTransition.IGNORE_DUPLICATE.value:
        return resolve_duplicate_task(
            task=task,
            message=message,
        )

    if transition_type == TaskTransition.CONTINUE_TASK.value:
        if task.query:
            merged_query = refine_task_query(task.query, message)

            if merged_query:
                return ConversationResolution(
                    query=merged_query,
                    should_search=True,
                    reason="continue_task",
                )

            return ConversationResolution(
                query=message,
                should_search=True,
                reason="fallback_message",
            )

    return ConversationResolution(
        query=message,
        should_search=True,
        reason="fallback_message",
    )