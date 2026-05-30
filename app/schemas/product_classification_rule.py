from pydantic import BaseModel

from app.schemas.product_classification import (
    SportType,
    UsageType,
    StyleGroup,
)


class ProductClassificationRule(BaseModel):
    keywords: list[str]

    style_group: StyleGroup
    sport_type: SportType
    usage_type: UsageType