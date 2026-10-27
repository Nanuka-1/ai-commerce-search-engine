from enum import Enum


class ConversationIntent(str, Enum):
    GREETING = "greeting"
    GRATITUDE = "gratitude"
    FAREWELL = "farewell"
    SMALL_TALK = "small_talk"
    SEARCH_RELATED = "search_related"
    UNKNOWN = "unknown"