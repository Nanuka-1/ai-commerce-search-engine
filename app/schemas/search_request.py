from pydantic import BaseModel

class SearchRequest(BaseModel):
    raw_query: str

    normalized_query: str | None = None
    intent: str | None = None

    size: str | None = None
    brand: str | None = None
    category: str | None = None
    color: str | None = None

    min_price: float | None = None
    max_price: float | None = None


    limit: int = 5
    offset: int = 0