"""29.10: пробный экзамен поиска по фото на ОДНОЙ модели (Adidas Samba).
Фото клиента (не с topsport.ge) → смысловая точка → сравниваем с картинками кандидатов из каталога:
  все модели Samba (похожие между собой — проверка «точно / похоже») + 100 случайных других обувных Adidas (шум).
Показывает: на каком месте правильная модель и с какой похожестью — по этим цифрам выберем границу честности.

Подготовка: папка photo_eval/ в корне проекта, в ней фото и answers.txt:
    1.jpg https://topsport.ge/ka/product/....      ← правильная модель
    2.jpg similar                                  ← та же Samba, но другой цвет / нет точной у нас
    3.jpg junk                                     ← не товар
Запуск:  doppler run -- python photo_probe.py
Ничего не меняет в базе, только читает. Картинки каталога кэшируются в photo_eval/.catalog_cache.json (повтор — быстро).
"""
import json
import math
import mimetypes
import os
import random
import time
import urllib.request
from pathlib import Path

from google import genai
from google.genai import types
from sqlalchemy import text

from app.db.session import engine

MODEL = "gemini-embedding-2"
DIMENSIONS = 768
FOLDER = Path("photo_eval")
CACHE = FOLDER / ".catalog_cache.json"
MODEL_WORD = "samba"
NOISE = 100                 # других обувных Adidas для «шума»


def candidates() -> list[dict]:
    sql = text("""
        SELECT DISTINCT ON (split_part(product_url, '?', 1))
               split_part(product_url, '?', 1) AS page, name, image_url
        FROM products
        WHERE is_active AND image_url IS NOT NULL AND image_url <> ''
          AND brand ILIKE 'adidas' AND category_slug ILIKE '%ფეხსაცმ%'
        ORDER BY split_part(product_url, '?', 1)
    """)
    with engine.connect() as connection:
        rows = [dict(row._mapping) for row in connection.execute(sql)]
    target = [row for row in rows if MODEL_WORD in (row["name"] or "").lower() or MODEL_WORD in row["page"]]
    others = [row for row in rows if row not in target]
    random.seed(29)
    return target + random.sample(others, min(NOISE, len(others)))


def embed(client, content) -> list[float]:
    for attempt in range(3):
        try:
            response = client.models.embed_content(
                model=MODEL, contents=[content],
                config=types.EmbedContentConfig(output_dimensionality=DIMENSIONS))
            return list(response.embeddings[0].values)
        except Exception as error:                  # лимит / сеть — подождать и повторить
            if attempt == 2:
                raise
            print(f"   повтор через 5 с: {str(error)[:80]}")
            time.sleep(5)


def image_part(data: bytes, mime: str):
    return types.Part.from_bytes(data=data, mime_type=mime)


def download(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read(), response.headers.get_content_type() or "image/jpeg"


def cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def catalog_vectors(client, rows: list[dict]) -> dict:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    todo = [row for row in rows if row["page"] not in cache]
    print(f"Кандидатов: {len(rows)} (Samba: {sum(MODEL_WORD in (r['name'] or '').lower() or MODEL_WORD in r['page'] for r in rows)}),"
          f" новых картинок: {len(todo)} (≈ {len(todo) * 1.2 / 60:.0f} мин)")
    for number, row in enumerate(todo, start=1):
        try:
            data, mime = download(row["image_url"])
            cache[row["page"]] = {"name": row["name"], "vector": embed(client, image_part(data, mime))}
        except Exception as error:
            print(f"   пропуск {row['page'].rsplit('/', 1)[-1]}: {str(error)[:80]}")
        if number % 20 == 0:
            print(f"   {number}/{len(todo)}")
            CACHE.write_text(json.dumps(cache), encoding="utf-8")   # сохраняем по пути — обрыв не страшен
    CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return {page: cache[page] for page in (row["page"] for row in rows) if page in cache}


def main() -> None:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    answers = {}
    for line in (FOLDER / "answers.txt").read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            name, expected = line.split(maxsplit=1)
            answers[name] = expected.strip().split("?")[0]
    catalog = catalog_vectors(client, candidates())

    for name, expected in answers.items():
        path = FOLDER / name
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        vector = embed(client, image_part(path.read_bytes(), mime))
        ranked = sorted(catalog.items(), key=lambda pair: cosine(vector, pair[1]["vector"]), reverse=True)
        print(f"\n=== {name}  (ожидаем: {expected.rsplit('/', 1)[-1] if expected.startswith('http') else expected})")
        place = next((i for i, (page, _) in enumerate(ranked, 1) if page == expected), None)
        if expected.startswith("http"):
            print(f"   правильная модель на месте: {place if place else 'НЕТ среди кандидатов'}")
        for i, (page, item) in enumerate(ranked[:8], start=1):
            mark = "  ← ПРАВИЛЬНАЯ" if page == expected else ""
            samba = " [samba]" if MODEL_WORD in (item["name"] or "").lower() or MODEL_WORD in page else ""
            print(f"   {i}. {cosine(vector, item['vector']):.3f}{samba}  {item['name'][:50]}  …{page[-30:]}{mark}")


if __name__ == "__main__":
    main()