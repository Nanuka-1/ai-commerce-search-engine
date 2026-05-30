from enum import Enum


class TaskStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    RESOLVED = "resolved"
    COMPLETED = "completed"
    CANCELLED = "cancelled"