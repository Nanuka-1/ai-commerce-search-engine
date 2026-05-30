from enum import Enum


class SearchResultMode(str, Enum):
    NEED_SIZE = "need_size"
    NEED_MODEL = "need_model"
    EXACT_MODEL_MATCH = "exact_model_match"
    FALLBACK_SIMILAR = "fallback_similar"
    BROAD_QUERY = "broad_query"
    NORMAL = "normal"