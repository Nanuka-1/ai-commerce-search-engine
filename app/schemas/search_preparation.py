from pydantic import BaseModel

from app.schemas.product_intent import ProductIntent


class SearchPreparation(BaseModel):
    normalized_query: str
    product_intent: ProductIntent | None = None
    usage_type: str | None = None
    model_hint: str | None = None
    brand: str | None = None
    category: str | None = None
    size: str | None = None
    color: str | None = None
    strategy_name: str | None = None