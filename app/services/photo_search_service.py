"""
29.10 (поиск по фото, шаг 2): фото клиента → похожие модели каталога + ЧЕСТНЫЙ вердикт.

  фото ─┬─ ИИ смотрит (Flash-Lite): товар ли это, тип (обувь / одежда / аксессуар), бренд, что написано
        └─ метка фото (Gemini Embedding 2)                         ← оба вызова ПАРАЛЛЕЛЬНО (как 16.10)
     → ближайшие метки картинок каталога (product_image_embeddings) среди подходящих по типу / бренду
     → вердикт: exact («აი ეს მოდელი») / similar («ზუსტად ვერ ვიპოვე — აი მსგავსი») / not_found / junk

Search decides → Business rules decide → LLM speaks: ИИ только описывает фото, товары выбирает база,
вердикт — наши пороги (замер 29.10, photo_probe.py: своя модель 0.840–0.870 на 1-м месте, разрыв со 2-м
0.022–0.025; белая Samba 0.707 — похожие; кофе 0.653). Пороги черновые — уточняются экзаменом photo_eval/.
"""
import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field

from sqlalchemy import text

from app.services import llm_client
from app.services.embedding_client import _get_client

IMAGE_EMBEDDING_MODEL = "gemini-embedding-2"     # то же, что ingestion/build_image_embeddings.py
IMAGE_EMBEDDING_DIM = 768
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024

EXACT_SIMILARITY = 0.83      # «точно эта модель» — только если похожесть высокая…
EXACT_GAP = 0.02             # …и заметно выше второй модели
SIMILAR_SIMILARITY = 0.70    # ниже — «похожего не нашла»
CANDIDATES = 20
PHOTO_BUDGET_SECONDS = 12    # ОБЩИЙ лимит на оба вызова ИИ (идут параллельно); 30.10: был у каждого свой → до 24 с

EXACT, SIMILAR, NOT_FOUND, JUNK = "exact", "similar", "not_found", "junk"
UNAVAILABLE = "unavailable"   # метку фото не получили (лимит Gemini / сеть) — честно: «сейчас не могу посмотреть фото»

# тип товара от ИИ → слово в category_slug каталога
TYPE_CATEGORY = {"footwear": "ფეხსაცმ", "clothing": "ტანსაცმ"}

PHOTO_INSTRUCTION = """You look at a photo sent to the chat of TopSport, a sports store (shoes, clothing, sports equipment).
Return ONLY a JSON object:
{"is_product": true|false, "product_type": "footwear"|"clothing"|"accessory"|"other"|null,
 "brand": string or null, "model_text": string or null, "color": string or null}
- is_product: true only if the photo clearly shows a shoe, a piece of clothing, a bag, a ball or other sports goods.
- brand: only if you can SEE it (logo, stripes, text) — otherwise null. Never guess.
- model_text: text printed on the product (e.g. "SAMBA") — only what is visible, otherwise null.
- color: main color in English, one or two words."""


@dataclass
class PhotoResult:
    verdict: str
    pages: list[tuple[str, float]] = field(default_factory=list)     # [(page_url, похожесть)]
    understanding: dict | None = None                                 # что увидел ИИ (или None — не успел)
    errors: list[str] = field(default_factory=list)


def check_photo(data: bytes, mime: str) -> str | None:
    """Ошибка для клиента (ключ translations) или None. Фото не сохраняем — только проверяем."""
    if mime not in ALLOWED_MIME:
        return "photo_bad_format"
    if not data or len(data) > MAX_PHOTO_BYTES:
        return "photo_too_big"
    return None


def parse_photo_understanding(raw: str | None) -> dict | None:
    if not raw:
        return None
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", raw.strip())
    try:
        data = json.loads(cleaned)
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("is_product"), bool):
        return None
    product_type = data.get("product_type")

    def _text(value):
        return value.strip() if isinstance(value, str) and value.strip() else None

    return {"is_product": data["is_product"],
            "product_type": product_type if product_type in {"footwear", "clothing", "accessory", "other"} else None,
            "brand": _text(data.get("brand")), "model_text": _text(data.get("model_text")),
            "color": _text(data.get("color"))}


def describe_photo(data: bytes, mime: str) -> dict | None:
    """ИИ описывает фото (первая модель цепочки, обычно Flash-Lite). Ошибка / выключено → None."""
    from google.genai import types

    if not llm_client.is_enabled():
        return None
    for model in llm_client.configured_models():
        if "gemma" in model.lower():
            continue                              # Gemma картинки не смотрит
        try:
            result = _get_client().models.generate_content(
                model=model,
                contents=[types.Part.from_bytes(data=data, mime_type=mime), PHOTO_INSTRUCTION],
                config=types.GenerateContentConfig(temperature=0, max_output_tokens=256),
            )
            parsed = parse_photo_understanding(result.text)
            if parsed is not None:
                return parsed
        except Exception:                          # лимит / сеть — следующая модель
            continue
    return None


def embed_photo(data: bytes, mime: str) -> list[float]:
    from google.genai import types

    result = _get_client().models.embed_content(
        model=IMAGE_EMBEDDING_MODEL, contents=[types.Part.from_bytes(data=data, mime_type=mime)],
        config=types.EmbedContentConfig(output_dimensionality=IMAGE_EMBEDDING_DIM))
    vector = list(result.embeddings[0].values)
    length = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / length for x in vector]


def build_photo_sql(category_word: str | None, brand: str | None, limit: int):
    conditions = ["p.is_active"]
    params = {"limit": limit}
    if category_word:
        conditions.append("p.category_slug ILIKE :category_like")
        params["category_like"] = f"%{category_word}%"
    if brand:
        conditions.append("lower(p.brand) = :brand")
        params["brand"] = brand.lower()
    sql = f"""
        WITH allowed AS (
            SELECT DISTINCT split_part(p.product_url, '?', 1) AS page
            FROM products p
            WHERE {" AND ".join(conditions)}
        )
        SELECT e.page_url, 1 - (e.embedding <=> CAST(:photo_vector AS vector)) AS similarity
        FROM product_image_embeddings e
        JOIN allowed a ON a.page = e.page_url
        ORDER BY e.embedding <=> CAST(:photo_vector AS vector)
        LIMIT :limit
    """
    return sql, params


def to_vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"


def nearest_pages(db, vector: list[float], understanding: dict | None, limit: int = CANDIDATES):
    """Ближайшие картинки каталога. Фильтры — из того, что ИИ ВИДЕЛ (тип, бренд); пусто с брендом →
    пробуем без бренда (ИИ мог прочитать бренд неверно), пусто с типом → без типа."""
    category = TYPE_CATEGORY.get((understanding or {}).get("product_type"))
    brand = (understanding or {}).get("brand")
    attempts = [(category, brand), (category, None), (None, None)]
    for category_word, brand_name in dict.fromkeys(attempts):
        sql, params = build_photo_sql(category_word, brand_name, limit)
        params["photo_vector"] = to_vector_literal(vector)
        rows = [(row.page_url, float(row.similarity)) for row in db.execute(text(sql), params)]
        if rows:
            return rows
    return []


def decide(pages: list[tuple[str, float]], understanding: dict | None) -> str:
    """Честный вердикт по цифрам. ИИ сказал «не товар» → junk, даже если что-то «похоже»."""
    if understanding is not None and not understanding["is_product"]:
        return JUNK
    if not pages or pages[0][1] < SIMILAR_SIMILARITY:
        return NOT_FOUND
    second = pages[1][1] if len(pages) > 1 else 0.0
    if pages[0][1] >= EXACT_SIMILARITY and pages[0][1] - second >= EXACT_GAP:
        return EXACT
    return SIMILAR


_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="photo-search")


def search_by_photo(db, data: bytes, mime: str) -> PhotoResult:
    """Фото → вердикт + страницы. Два вызова ИИ параллельно; метка фото обязательна, описание — по возможности.
    Лимит ОБЩИЙ: описание ждём только остаток времени после метки (живьём 30.10: кофе ждал 17.6 с —
    сначала метку, потом ещё до 12 с описание)."""
    errors = []
    deadline = time.monotonic() + PHOTO_BUDGET_SECONDS
    description = _executor.submit(describe_photo, data, mime)
    embedding = _executor.submit(embed_photo, data, mime)
    try:
        vector = embedding.result(timeout=PHOTO_BUDGET_SECONDS)
    except FutureTimeout:
        return PhotoResult(UNAVAILABLE, errors=["embedding: timeout"])
    except Exception as error:
        return PhotoResult(UNAVAILABLE, errors=[f"embedding: {str(error)[:120]}"])
    try:
        understanding = description.result(timeout=max(0.0, deadline - time.monotonic()))
    except FutureTimeout:
        understanding, errors = None, errors + ["understanding: timeout"]
    pages = nearest_pages(db, vector, understanding)
    return PhotoResult(decide(pages, understanding), pages, understanding, errors)