from app.schemas.product_classification import (
    SportType,
    UsageType,
    StyleGroup,
    ProductType,
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
    # Беговая обувь (04.10): магазин почти не пишет "для бега" (19 из ~2800 страниц),
    # поэтому вид спорта берём из беговых моделей и слов "бег" в названии.
    # Стоит последним: более конкретные правила моделей выше имеют приоритет.
    ProductClassificationRule(
        keywords=[
            "pegasus", "vomero", "supernova", "adizero", "duramo", "fortarun",
            "softride", "nitro", "charged", "revolution", "infinite",
            "running", "სარბენ", "სირბილ",
        ],
        style_group=None,
        sport_type=SportType.RUNNING,
        usage_type=UsageType.PERFORMANCE,
    ),
]

# 07.10: открытая обувь (шлёпанцы, сандалии) НЕ бывает беговой, даже если в названии
# беговая модель (adiFOM SUPERNOVA — сандалия, а не кроссовок Supernova).
# Проверяется по названию и по категории; такие товары идут дальше к правилам категории (casual).
NOT_RUNNING_FOOTWEAR_WORDS = [
    "ჩუსტ", "სანდალ", "შლაპუნა", "შლოპანც",
    "slide", "sandal", "flip", "adifom",
]


def _is_open_footwear(normalized_query: str, category_slug: str | None) -> bool:
    text = f"{normalized_query} {(category_slug or '').lower()}"
    return any(word in text for word in NOT_RUNNING_FOOTWEAR_WORDS)


CATEGORY_TYPE_KEYWORDS: list[tuple[str, ProductType]] = [
    ("ფეხსაცმელი", ProductType.FOOTWEAR),
    ("ჩუსტ", ProductType.FOOTWEAR),
    ("შლაპუნა", ProductType.FOOTWEAR),
    ("ბოტ", ProductType.FOOTWEAR),
    ("შლოპანც", ProductType.FOOTWEAR),

    ("ტანსაცმელი", ProductType.CLOTHING),
    ("მაისური", ProductType.CLOTHING),
    ("შარვალი", ProductType.CLOTHING),
    ("ჯემპრი", ProductType.CLOTHING),
    ("ქურთუკი", ProductType.CLOTHING),
    ("შორტი", ProductType.CLOTHING),
    ("კოსტიუმი", ProductType.CLOTHING),
    ("პლავკ", ProductType.CLOTHING),

    ("აქსესუარ", ProductType.ACCESSORY),
    ("ჩანთა", ProductType.ACCESSORY),
    ("ქუდი", ProductType.ACCESSORY),
    ("წინდა", ProductType.ACCESSORY),
    ("ხელთათმანი", ProductType.ACCESSORY),
    ("შარფი", ProductType.ACCESSORY),
    ("ბოთლი", ProductType.ACCESSORY),
    ("პირსახოცი", ProductType.ACCESSORY),
    ("მანჟეტი", ProductType.ACCESSORY),

    ("სპორტული კვება", ProductType.NUTRITION),
    ("ამინომჟავა", ProductType.NUTRITION),
    ("შეიკერი", ProductType.NUTRITION),

    ("სავარჯიშო მოწყობილობები", ProductType.EQUIPMENT),
    ("ველოსიპედი", ProductType.EQUIPMENT),
    ("სკეითბორდი", ProductType.EQUIPMENT),
    ("ბილიარდ", ProductType.EQUIPMENT),
    ("ბურთი", ProductType.EQUIPMENT),
]

def classify_product_type(category_slug: str | None) -> ProductType:
    if not category_slug:
        return ProductType.OTHER
    normalized_category = category_slug.lower()
    for keyword, product_type in CATEGORY_TYPE_KEYWORDS:
        if keyword in normalized_category:
            return product_type
    return ProductType.OTHER


CASUAL_FOOTWEAR_CATEGORY_KEYWORDS = ["ჩუსტ", "შლაპუნა", "შლოპანც"]
SPORT_FOOTWEAR_CATEGORY_KEYWORDS = ["სპორტული", "ბოტასი"]

DEFAULT_CASUAL_FOOTWEAR_INTENT = ProductIntent(
    style_group=StyleGroup.LIFESTYLE_SNEAKERS,
    sport_type=SportType.CASUAL,
    usage_type=UsageType.LIFESTYLE,
)

DEFAULT_SPORT_FOOTWEAR_INTENT = ProductIntent(
    style_group=None,
    sport_type=None,
    usage_type=UsageType.PERFORMANCE,
)

# "ბოტები" (ботинки), но НЕ "ბოტასი" (кроссовки)
BOOTS_FOOTWEAR_CATEGORY_KEYWORDS = ["ბოტებ"]

DEFAULT_BOOTS_FOOTWEAR_INTENT = ProductIntent(
    style_group=None,
    sport_type=SportType.CASUAL,
    usage_type=UsageType.LIFESTYLE,
)

def extract_product_intent(query: str, category_slug: str | None = None) -> ProductIntent | None:
    normalized_query = query.lower()

    if category_slug is not None and classify_product_type(category_slug) != ProductType.FOOTWEAR:
        return None

    open_footwear = _is_open_footwear(normalized_query, category_slug)

    for rule in KEYWORD_CLASSIFICATION_RULES:
        if open_footwear and rule.sport_type == SportType.RUNNING:
            continue   # шлёпанцы/сандалии с беговым словом в названии — не беговые
        for keyword in rule.keywords:
            if keyword in normalized_query:
                return ProductIntent(
                    style_group=rule.style_group,
                    sport_type=rule.sport_type,
                    usage_type=rule.usage_type,
                )

    if category_slug is None or classify_product_type(category_slug) != ProductType.FOOTWEAR:
        return None

    normalized_category = category_slug.lower()

    if any(keyword in normalized_category for keyword in CASUAL_FOOTWEAR_CATEGORY_KEYWORDS):
        return DEFAULT_CASUAL_FOOTWEAR_INTENT

    if any(keyword in normalized_category for keyword in SPORT_FOOTWEAR_CATEGORY_KEYWORDS):
        return DEFAULT_SPORT_FOOTWEAR_INTENT

    if any(keyword in normalized_category for keyword in BOOTS_FOOTWEAR_CATEGORY_KEYWORDS):
        return DEFAULT_BOOTS_FOOTWEAR_INTENT

    return None