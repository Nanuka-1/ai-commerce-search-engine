from app.db.models import SearchTask

from app.schemas.task_transition import TaskTransition

from app.services.task_transition_service import (
    classify_task_transition,
)
from app.services.search_constraints_service import (
    extract_constraints_from_message,
)

from app.services.search_query_builder_service import (
    merge_constraints,
    build_query_from_constraints,
)
from app.schemas.conversation_resolution import ConversationResolution

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
            current_constraints = extract_constraints_from_message(task.query)
            incoming_constraints = extract_constraints_from_message(message)

            merged_constraints = merge_constraints(
                current=current_constraints,
                incoming=incoming_constraints,
            )

            merged_query = build_query_from_constraints(merged_constraints)

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