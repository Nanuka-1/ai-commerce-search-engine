from enum import Enum


class FallbackLevel(str, Enum):
    EXACT_MODEL = "exact_model"
    SAME_BRAND_SAME_SIZE = "same_brand_same_size"
    SAME_STYLE_SAME_SIZE = "same_style_same_size"
    SAME_CATEGORY_SAME_SIZE = "same_category_same_size"
    BRAND_ONLY = "brand_only"
    SAME_SIZE = "same_size"
    NO_RESULTS = "no_results"