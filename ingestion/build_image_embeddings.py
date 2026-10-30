"""
29.10 (поиск по фото, шаг 1): точки КАРТИНОК каталога — та же «карта смыслов», что у текстов (build_embeddings.py),
только метку ставит картинка товара. Фото клиента потом получает свою точку → ближайшие метки = похожие товары.

Пробный экзамен 29.10 (photo_probe.py): фото Samba «на ноге» → правильная модель на 1-м месте (0.870 / 0.840).

Как устроено (по образцу build_embeddings.py):
  1. Одна картинка на модель (страницу сайта): вариант с наименьшим id.
  2. Отпечаток = адрес картинки + модель Gemini: картинка не менялась → не пересчитываем.
  3. Одинаковая картинка у нескольких страниц → Gemini считает один раз, точка копируется.
  4. Сначала обувь (по фото чаще всего ищут кроссовки), потом остальное.
  5. Лимит Gemini (429): ждём и повторяем; не прошло после нескольких попыток → останавливаемся,
     всё сделанное уже сохранено (commit каждые SAVE_EVERY) — следующий запуск продолжит.
  6. Снятые с продажи модели — их точки удаляются.

Запуск из корня проекта:  doppler run -- python -m ingestion.build_image_embeddings
  с нормой и словом «сначала»:  … build_image_embeddings 600 samba   (600 картинок, модели со словом samba — первыми;
  оставшиеся 400 из 1 000 в день — на проверку фото в чате)
"""
import os
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text

from app.db.models import Product
from app.db.session import SessionLocal
from ingestion.build_embeddings import page_of, pick_page_cards, to_vector_literal

IMAGE_EMBEDDING_MODEL = "gemini-embedding-2"
DIMENSIONS = 768            # замер 29.10: 768 хватает (Samba 1-я); меньше места и быстрее поиск
WORKERS = 4                 # параллельно (картинка ≈ 1.2 с; 4 потока ≈ в 4 раза быстрее, если пустит лимит)
SAVE_EVERY = 40             # сохранять в базу каждые N картинок — обрыв не теряет сделанное
RETRIES = 4                 # попыток на картинку при лимите / сети
RETRY_PAUSE = 30            # с между попытками при 429
FOOTWEAR_WORD = "ფეხსაცმ"
# Лимиты бесплатного gemini-embedding-2 (AI Studio → Rate Limit, 29.10): 100 в минуту, 30K токенов в минуту,
# 1 000 в ДЕНЬ — общий с поиском по фото клиентов. Оставляем запас ~150 на клиентов, остальное — каталогу.
DAILY_BUDGET = 850

CREATE_SQL = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    f"""CREATE TABLE IF NOT EXISTS product_image_embeddings (
            page_url   TEXT PRIMARY KEY,
            image_url  TEXT NOT NULL,
            model      TEXT NOT NULL,
            embedding  vector({DIMENSIONS}) NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )""",
    """CREATE INDEX IF NOT EXISTS ix_product_image_embeddings_hnsw
           ON product_image_embeddings USING hnsw (embedding vector_cosine_ops)""",
]

UPSERT_SQL = text("""
    INSERT INTO product_image_embeddings (page_url, image_url, model, embedding, updated_at)
    VALUES (:page_url, :image_url, :model, CAST(:embedding AS vector), now())
    ON CONFLICT (page_url) DO UPDATE
       SET image_url = EXCLUDED.image_url, model = EXCLUDED.model,
           embedding = EXCLUDED.embedding, updated_at = now()
""")


class QuotaStop(Exception):
    """Лимит Gemini не отпустил после всех попыток — остановиться, продолжить в следующий запуск."""


def first_by_word(plan: list[tuple[str, list[str]]], word: str | None) -> list[tuple[str, list[str]]]:
    """Картинки моделей со словом в адресе страницы («samba») — в начало очереди (для проверки)."""
    if not word:
        return plan
    word = word.lower()
    return sorted(plan, key=lambda item: not any(word in page.lower() for page in item[1]))


def plan_images(cards: dict, saved: dict, model: str) -> list[tuple[str, list[str]]]:
    """Что считать: [(image_url, [pages])] — только новые / изменённые, одинаковая картинка — один раз,
    сначала обувь. cards: {page: product}; saved: {page: (image_url, model)}."""
    groups = defaultdict(list)
    footwear = set()
    for page, card in cards.items():
        image = (card.image_url or "").strip()
        if not image or saved.get(page) == (image, model):
            continue
        groups[image].append(page)
        if FOOTWEAR_WORD in (card.category_slug or ""):
            footwear.add(image)
    return sorted(groups.items(), key=lambda item: (item[0] not in footwear, item[0]))


def download(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read(), response.headers.get_content_type() or "image/jpeg"


def embed_image(client, data: bytes, mime: str) -> list[float]:
    from google.genai import types

    for attempt in range(1, RETRIES + 1):
        try:
            response = client.models.embed_content(
                model=IMAGE_EMBEDDING_MODEL, contents=[types.Part.from_bytes(data=data, mime_type=mime)],
                config=types.EmbedContentConfig(output_dimensionality=DIMENSIONS))
            return list(response.embeddings[0].values)
        except Exception as error:
            quota = "429" in str(error) or "RESOURCE_EXHAUSTED" in str(error)
            if attempt == RETRIES:
                raise QuotaStop(str(error)[:200]) if quota else error
            time.sleep(RETRY_PAUSE if quota else 3)


def embed_one(client, image_url: str):
    """(image_url, vector) или (image_url, None) — картинка не скачалась / битая (пропускаем, не останавливаемся)."""
    try:
        data, mime = download(image_url)
    except Exception as error:
        print(f"   не скачалась: …{image_url[-40:]} ({str(error)[:60]})")
        return image_url, None
    return image_url, embed_image(client, data, mime)


def main(budget: int = DAILY_BUDGET, first_word: str | None = None) -> None:
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    db = SessionLocal()
    started = time.perf_counter()
    for statement in CREATE_SQL:
        db.execute(text(statement))
    db.commit()

    cards = pick_page_cards(db.query(Product).filter(Product.is_active.is_(True)).all())
    saved = {row.page_url: (row.image_url, row.model)
             for row in db.execute(text("SELECT page_url, image_url, model FROM product_image_embeddings"))}

    stale = [page for page in saved if page not in cards]
    if stale:
        db.execute(text("DELETE FROM product_image_embeddings WHERE page_url = ANY(:pages)"), {"pages": stale})
        db.commit()
        print(f"Удалено точек снятых моделей: {len(stale)}")

    plan = plan_images(cards, saved, IMAGE_EMBEDDING_MODEL)
    pages_total = sum(len(pages) for _, pages in plan)
    print(f"Моделей: {len(cards)}, уже есть точки: {len(cards) - pages_total}, "
          f"нужно ещё: {len(plan)} картинок; сегодня — не больше {budget} (запас на клиентов / проверку)")
    plan = first_by_word(plan, first_word)
    postponed = max(0, len(plan) - budget)
    plan = plan[:budget]

    done, rows, stopped = 0, [], None
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for start in range(0, len(plan), SAVE_EVERY):
            chunk = plan[start:start + SAVE_EVERY]
            pages_by_image = dict(chunk)
            try:
                results = list(pool.map(lambda item: embed_one(client, item[0]), chunk))
            except QuotaStop as error:
                stopped = str(error)
                break
            rows = [{"page_url": page, "image_url": image, "model": IMAGE_EMBEDDING_MODEL,
                     "embedding": to_vector_literal(vector)}
                    for image, vector in results if vector is not None
                    for page in pages_by_image[image]]
            if rows:
                db.execute(UPSERT_SQL, rows)
                db.commit()
            done += len(chunk)
            minutes = (time.perf_counter() - started) / 60
            print(f"…картинок {done} из {len(plan)} ({minutes:.0f} мин)")

    total = db.execute(text("SELECT COUNT(*) FROM product_image_embeddings")).scalar()
    db.close()
    print(f"\nТочек картинок в таблице: {total} из {len(cards)} моделей "
          f"({(time.perf_counter() - started) / 60:.0f} мин)")
    if stopped:
        print(f"Остановлено: лимит Gemini ({stopped[:120]}). Сделанное сохранено — запустите позже, продолжит.")
    elif postponed:
        print(f"Дневная норма выполнена. Осталось {postponed} картинок — запустите завтра "
              f"(≈ {postponed / DAILY_BUDGET:.0f} дн. по {DAILY_BUDGET}).")


if __name__ == "__main__":
    import sys

    main(budget=int(sys.argv[1]) if len(sys.argv) > 1 else DAILY_BUDGET,
         first_word=sys.argv[2] if len(sys.argv) > 2 else None)