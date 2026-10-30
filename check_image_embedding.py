"""28.10: разведка поиска по фото — работает ли Gemini Embedding 2 с КАРТИНКАМИ на нашем ключе.
Замер 28.10: 9 515 моделей, картинка у всех 9 515, известное имя модели (model_family) только у 698 (7%)
→ по тексту точную модель не найти, нужен путь «картинка ↔ картинка».

Что проверяет (ничего не меняет в базе, только читает):
  1. ключ принимает модель gemini-embedding-2 и картинки (или ошибка: нет доступа / платно / лимит);
  2. сколько секунд на одну картинку → сколько займёт весь каталог;
  3. текст и картинки в ОДНОМ пространстве: запрос словами находит подходящие картинки каталога?

Запуск из корня проекта:  doppler run -- python check_image_embedding.py
"""
import math
import os
import random
import time
import urllib.request

from google import genai
from google.genai import types
from sqlalchemy import text

from app.db.session import engine

MODEL = "gemini-embedding-2"
DIMENSIONS = 768            # меньше 3072: быстрее и дешевле хранить; для замера хватит
SAMPLE = 30                 # картинок каталога в пробе
TEXT_QUERIES = ["white sneakers", "ქალის შავი ქურთუკი", "football ball", "kids pink sandals"]


def load_sample(size: int) -> list[dict]:
    """Случайные модели с картинкой: страница, название, бренд, картинка."""
    sql = text("""
        SELECT DISTINCT ON (split_part(product_url, '?', 1))
               split_part(product_url, '?', 1) AS page, name, brand, image_url
        FROM products
        WHERE is_active AND image_url IS NOT NULL AND image_url <> ''
        ORDER BY split_part(product_url, '?', 1)
    """)
    with engine.connect() as connection:
        rows = [dict(row._mapping) for row in connection.execute(sql)]
    random.seed(28)
    return random.sample(rows, min(size, len(rows)))


def download(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        mime = response.headers.get_content_type() or "image/jpeg"
        return response.read(), mime


def embed(client, content) -> list[float]:
    response = client.models.embed_content(
        model=MODEL, contents=[content],
        config=types.EmbedContentConfig(output_dimensionality=DIMENSIONS))
    return list(response.embeddings[0].values)


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def main() -> None:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    sample = load_sample(SAMPLE)
    print(f"Модель {MODEL}, {DIMENSIONS} измерений, картинок в пробе: {len(sample)}\n")

    vectors, seconds, errors = [], [], []
    for item in sample:
        try:
            data, mime = download(item["image_url"])
            started = time.perf_counter()
            vector = embed(client, types.Part.from_bytes(data=data, mime_type=mime))
            seconds.append(time.perf_counter() - started)
            vectors.append((item, vector))
        except Exception as error:                     # замер: ошибку показываем и идём дальше
            errors.append(f"{item['page'].rsplit('/', 1)[-1]}: {str(error)[:160]}")
        if len(errors) >= 3 and not vectors:
            break                                       # три ошибки подряд и ни одного успеха — дальше нет смысла

    print(f"Успешно: {len(vectors)}, ошибок: {len(errors)}")
    for line in errors[:5]:
        print("  ошибка →", line)
    if not vectors:
        return

    average = sum(seconds) / len(seconds)
    print(f"Время на картинку: среднее {average:.2f} с, мин {min(seconds):.2f}, макс {max(seconds):.2f}")
    print(f"Весь каталог (9 515 моделей) по одной: ≈ {9515 * average / 60:.0f} мин (без учёта лимитов в минуту)\n")

    print("Текст → картинки каталога (лучшие 3 из пробы):")
    for query in TEXT_QUERIES:
        query_vector = embed(client, query)
        ranked = sorted(vectors, key=lambda pair: cosine(query_vector, pair[1]), reverse=True)[:3]
        print(f"  «{query}»")
        for item, vector in ranked:
            print(f"     {cosine(query_vector, vector):.3f}  {item['brand']} · {item['name'][:45]}")


if __name__ == "__main__":
    main()