from app.schemas.product_classification import (
    SportType,
    UsageType,
    StyleGroup,
)
from app.schemas.product_intent import ProductIntent
from app.schemas.product_classification_rule import ProductClassificationRule


KEYWORD_CLASSIFICATION_RULES = [
    ProductClassificationRule(
        keywords=["jordan"],
        style_group=StyleGroup.BASKETBALL_LIFESTYLE,
        sport_type=SportType.BASKETBALL,
        usage_type=UsageType.LIFESTYLE,
    ),
    ProductClassificationRule(
        keywords=["air max"],
        style_group=StyleGroup.LIFESTYLE_SNEAKERS,
        sport_type=SportType.CASUAL,
        usage_type=UsageType.LIFESTYLE,
    ),
    ProductClassificationRule(
        keywords=["predator"],
        style_group=StyleGroup.FOOTBALL_BOOTS,
        sport_type=SportType.FOOTBALL,
        usage_type=UsageType.PERFORMANCE,
    ),
    ProductClassificationRule(
        keywords=["ultraboost"],
        style_group=StyleGroup.RUNNING_LIFESTYLE,
        sport_type=SportType.RUNNING,
        usage_type=UsageType.LIFESTYLE,
    ),
    ProductClassificationRule(
        keywords=["superstar"],
        style_group=StyleGroup.LIFESTYLE_SNEAKERS,
        sport_type=SportType.CASUAL,
        usage_type=UsageType.LIFESTYLE,
    ),

# Category / generic footwear heuristics
    ProductClassificationRule(
        keywords=[
        "sportuli-fekhsatsmeli",
        "fekhsatsmeli",
        "სპორტული ფეხსაცმელი",
    ],
    style_group=StyleGroup.LIFESTYLE_SNEAKERS,
    sport_type=SportType.CASUAL,
    usage_type=UsageType.LIFESTYLE,
),

]




def extract_product_intent(query: str) -> ProductIntent | None:
    normalized_query = query.lower()

    for rule in KEYWORD_CLASSIFICATION_RULES:
        for keyword in rule.keywords:
            if keyword in normalized_query:
                return ProductIntent(
                    style_group=rule.style_group,
                    sport_type=rule.sport_type,
                    usage_type=rule.usage_type,
                )

    return None