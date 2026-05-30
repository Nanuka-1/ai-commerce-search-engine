from pydantic import BaseModel
from typing import List


class ProductCreate(BaseModel):
    sku: str
    name: str
    price: float

    brand: str | None = None
    category_slug: str | None = None
    size: str | None = None

    product_url: str | None = None
    image_url: str | None = None

    style_group: str | None = None
    sport_type: str | None = None
    usage_type: str | None = None


class Product(BaseModel):
    id: int
    sku: str
    name: str
    price: float

    model_config = {"from_attributes": True}


class ProductSearchResponse(BaseModel):
    query: str
    total: int
    items: List[Product]