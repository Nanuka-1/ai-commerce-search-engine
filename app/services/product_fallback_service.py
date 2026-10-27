from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.repositories.product_repository import (
    get_products_by_size,
    search_same_brand_size_products,
)
from app.schemas.fallback_level import FallbackLevel


class FallbackSearchResult(BaseModel):
    items: list
    total_count: int
    fallback_level: str
    alternative_reason: str
    matched_by: str


@dataclass
class FallbackStep:
    fetch: Callable[[], tuple[list, int]]
    fallback_level: str
    alternative_reason: str
    matched_by: str


def execute_fallback_chain(steps: list[FallbackStep]) -> FallbackSearchResult:
    for step in steps:
        items, total_count = step.fetch()

        if total_count > 0:
            return FallbackSearchResult(
                items=items,
                total_count=total_count,
                fallback_level=step.fallback_level,
                alternative_reason=step.alternative_reason,
                matched_by=step.matched_by,
            )

    return FallbackSearchResult(
        items=[],
        total_count=0,
        fallback_level=FallbackLevel.NO_RESULTS.value,
        alternative_reason="no_fallback_results",
        matched_by="no_results",
    )


def execute_model_fallback_search(
    db: Session,
    detected_brand: str | None,
    size: str | None,
    effective_category: str | None,
    style_group: str | None = None,
    limit: int = 200,
) -> FallbackSearchResult:
    steps: list[FallbackStep] = []

    if detected_brand:
        steps.append(
            FallbackStep(
                fetch=lambda: search_same_brand_size_products(
                    db=db,
                    brand=detected_brand,
                    size=size,
                    category=effective_category,
                    style_group=style_group,
                    limit=limit,
                ),
                fallback_level=FallbackLevel.SAME_BRAND_SAME_SIZE.value,
                alternative_reason="exact_model_not_found",
                matched_by="similar_model_same_brand_size",
            )
        )

    if effective_category:
        # Intentionally do not filter by style_group on broader fallback:
        # category/size fallback should widen the candidate pool.
        steps.append(
            FallbackStep(
                fetch=lambda: get_products_by_size(
                    db=db,
                    size=size,
                    category=effective_category,
                    limit=limit,
                ),
                fallback_level=FallbackLevel.SAME_CATEGORY_SAME_SIZE.value,
                alternative_reason="same_brand_not_found",
                matched_by="same_category_same_size",
            )
        )

    if size:
        steps.append(
            FallbackStep(
                fetch=lambda: get_products_by_size(
                    db=db,
                    size=size,
                    category=None,
                    limit=limit,
                ),
                fallback_level=FallbackLevel.SAME_SIZE.value,
                alternative_reason="same_category_not_found",
                matched_by="same_size",
            )
        )

    return execute_fallback_chain(steps)