from typing import Any
from pydantic import BaseModel, Field
from typing import Optional
from app.schemas.product_intent import ProductIntent


class SearchContext(BaseModel):
    query: str | None = None
    normalized_query: str | None = None

    intent: str | None = None

    requested_sku: str | None = None
    base_sku: str | None = None
    model_hint: str | None = None

    product_intent: ProductIntent | None = None

    detected_size: str | None = None
    detected_category: str | None = None
    detected_color: str | None = None

    matched_by: str | None = None  # "query", "sku", "price_check"

    result_mode: str | None = None
    needs_clarification: bool = False
    clarification_reason: Optional[str] = None

    search_strategy: str | None = None

    items: list[Any] = Field(default_factory=list)
    total_count: int = 0

    limit: int = 5
    offset: int = 0