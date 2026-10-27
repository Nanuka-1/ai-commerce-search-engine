from typing import Optional

from pydantic import BaseModel

from app.schemas.product_classification import (
    SportType,
    UsageType,
    StyleGroup,
)


class ProductIntent(BaseModel):
    style_group: Optional[StyleGroup] = None
    sport_type: Optional[SportType] = None
    usage_type: UsageType