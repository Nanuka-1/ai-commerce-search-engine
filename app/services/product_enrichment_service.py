from app.schemas.product_classification import ProductType
from app.services.product_intent_service import classify_product_type

# Модели обуви из каталога (SQL по названиям, 02.10; только модели с ≥3 страницами
# + прежние Nike). Ядро названия без версии: "superstar" покрывает II / 360 / Winter.
# Порядок важен: сначала более длинные/конкретные фразы. Общее слово "court" не берём.
# Единый список: используется и скрапером (model_family), и поиском (model_hint).
MODEL_FAMILIES = [
    # Nike
    "air force", "air max", "court borough", "court vision", "vapormax", "pegasus", "victori",
    "shox", "react", "jordan", "zoom", "blazer", "revolution", "royale",
    # Adidas
    "handball spezial", "stan smith", "grand court", "vl court", "court revival",
    "run 70s", "sl 72", "swift run", "superstar", "samba", "campus", "gazelle",
    "adilette", "ultraboost", "supernova", "duramo", "adizero", "f50", "predator",
    "advantage", "barreda", "fortarun", "ultimashow", "znchill", "adifom", "adicane",
    "terrex", "forum", "nmd", "climacool", "tensaur", "altaswim", "racer",
    # Puma
    "softride", "trinity", "rs x", "nitro", "spirex", "rebound",
    # Crocs
    "classic clog", "echo clog", "crocband", "all terrain", "crush", "inmotion", "getaway", "echo",
    # Under Armour
    "charged", "ansa", "infinite",
]


# Версии моделей, которые попадают в диапазон размеров и РЕАЛЬНО есть в каталоге
# (SQL 07.10 по названиям активных товаров). Число после слова — версия, только если
# такая пара есть здесь: "pegasus 41" → версия (спросим размер), "pegasus 42" → размер 42.
# Пересматривать тем же SQL раз в месяц (журнал п.62): появится Pegasus 42 — добавить.
VERSIONED_MODELS = {
    "pegasus": {"41"},
    "ultraboost": {"21", "22"},
    "ub": {"23"},
    "structure": {"24"},
    "zx": {"22"},
}

COLOR_KEYWORDS = {
    "black": "black",
    "gray": "gray",
    "grey": "gray",
    "red": "red",
    "white": "white",
    "navy": "navy",
    "green": "green",
    "pink": "pink",
    "olive": "olive",
    "silver": "silver",
    "gold": "gold",
    "blue": "blue",
    "coffee": "coffee",
    "orange": "orange",
    "purple": "purple",
    "mint": "mint",
    "multicolor": "multicolor",
}

def extract_color(name: str) -> str | None:
    normalized_name = name.lower()

    for keyword, canonical_color in COLOR_KEYWORDS.items():
        if keyword in normalized_name:
            return canonical_color

    return None

def extract_model_family(text: str) -> str | None:
    normalized_text = text.lower().replace("-", " ").replace("_", " ")

    for family in MODEL_FAMILIES:
        if family in normalized_text:
            return family

    return None


# Запасной вариант, когда на странице товара поле კატეგორია пустое
# (01.10: 841 страница Puma). Пол берём из названия; если пол не указан —
# по данным (размеры обуви 40–47) это мужские товары, а аксессуары — Unisex.
GENDER_NAME_KEYWORDS = [
    ("ბავშვ", "ბავშვი"),
    ("ქალ", "ქალი"),
    ("მამაკაც", "მამაკაცი"),
]
GENDERED_PRODUCT_TYPES = {ProductType.FOOTWEAR, ProductType.CLOTHING}


def infer_category_from_name(name: str | None) -> str | None:
    if not name:
        return None

    normalized_name = name.lower()
    gender = next(
        (label for keyword, label in GENDER_NAME_KEYWORDS if keyword in normalized_name),
        None,
    )

    if gender is None:
        if classify_product_type(name) in GENDERED_PRODUCT_TYPES:
            gender = "მამაკაცი"
        else:
            gender = "Unisex"

    return f"{gender}, {name}"