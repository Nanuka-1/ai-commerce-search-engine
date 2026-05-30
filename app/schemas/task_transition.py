from enum import Enum


class TaskTransition(str, Enum):
    NEW_TASK = "new_task"
    RESTART_TASK = "restart_task"
    CONTINUE_TASK = "continue_task"
    IGNORE_DUPLICATE = "ignore_duplicate"