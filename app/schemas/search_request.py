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
    max_price: float | None = None      # U2.3 (12.10): «до 100 лари» — понимает ИИ, фильтрует база
    discount_only: bool = False          # U2.3: «со скидкой» — только regular_price > price
    prefer_discount: bool = False        # 13.10: «сначала со скидкой, если есть» — скидки первыми, остальные после
    new_only: bool = False               # 21.10: «ახალი კოლექცია» — только новинки магазина (products.is_new)
    exclude_brands: list[str] = []       # 21.10: «სხვა ბრენდის» — без уже показанных брендов


    limit: int = 5
    offset: int = 0