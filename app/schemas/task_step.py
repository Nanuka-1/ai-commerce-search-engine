from enum import Enum


class TaskStep(str, Enum):
    WAITING_SIZE = "waiting_size"
    WAITING_REFINEMENT = "waiting_refinement"
    WAITING_MODEL = "waiting_model"
    WAITING_CLARIFICATION = "waiting_clarification"
    COMPLETED = "completed"