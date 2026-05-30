from pydantic import BaseModel


class SearchConstraints(BaseModel):
    brand: str | None = None
    category: str | None = None
    size: str | None = None
    color: str | None = None
    model_hint: str | None = None
    usage_type: str | None = None
    sport_type: str | None = None