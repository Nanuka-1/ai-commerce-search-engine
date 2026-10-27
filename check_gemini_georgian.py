"""
Понимает ли Gemini грузинский? Мини-поиск без базы: 9 товаров (названия как в каталоге)
и 10 запросов клиента (en + ka). Для каждого запроса — 2 ближайших товара по смыслу.
Всего 2 обращения к Gemini (товары одной пачкой, запросы одной пачкой). В базу не пишет.
"""
import math
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

MODEL = "gemini-embedding-001"

PRODUCTS = {
    "P1": "Nike მამაკაცის სპორტული ფეხსაცმელი AIR ZOOM PEGASUS 41",
    "P2": "Adidas ქალის სპორტული ფეხსაცმელი SUPERNOVA RISE",
    "P3": "Nike მამაკაცის ქურთუკი",
    "P4": "Adidas მამაკაცის ჯემპრი HOODIE",
    "P5": "Crocs კლოგი Classic Clog",
    "P6": "Nike სანდალი/ჩუსტი",
    "P7": "Puma ბავშვის ბოტასი",
    "P8": "Adidas ბურთი Tango Glider",
    "P9": "Under Armour ქალის შორტი",
}

# запрос -> какие товары считаем правильным ответом
QUERIES = [
    ("running shoes", {"P1", "P2"}),
    ("სარბენი ფეხსაცმელი", {"P1", "P2"}),
    ("warm jacket", {"P3"}),
    ("ზამთრის ქურთუკი", {"P3"}),
    ("hoodie", {"P4"}),
    ("football ball", {"P8"}),
    ("ფეხბურთის ბურთი", {"P8"}),
    ("beach slippers", {"P5", "P6"}),
    ("ბავშვის ფეხსაცმელი", {"P7"}),
    ("women shorts", {"P9"}),
]


def embed(client, texts, task_type):
    """По одному тексту с паузой: бесплатный уровень ограничивает число запросов в минуту."""
    import time

    vectors = []
    for text in texts:
        for attempt in range(5):
            try:
                result = client.models.embed_content(
                    model=MODEL,
                    contents=text,
                    config=types.EmbedContentConfig(task_type=task_type),
                )
                vectors.append(result.embeddings[0].values)
                break
            except Exception as error:
                if "429" not in str(error) or attempt == 4:
                    raise
                print(f"  лимит, жду 30 с… ({text[:30]})")
                time.sleep(30)
        time.sleep(1)
    return vectors


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def main():
    load_dotenv()
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    ids = list(PRODUCTS)
    product_vectors = embed(client, [PRODUCTS[i] for i in ids], "RETRIEVAL_DOCUMENT")
    query_vectors = embed(client, [q for q, _ in QUERIES], "RETRIEVAL_QUERY")

    correct = 0
    print(f"{'запрос':<24}{'итог':<6}2 ближайших товара (сходство)")
    print("-" * 110)
    for (query, expected), q_vec in zip(QUERIES, query_vectors):
        ranked = sorted(
            ((cosine(q_vec, p_vec), pid) for pid, p_vec in zip(ids, product_vectors)),
            reverse=True,
        )
        top_id = ranked[0][1]
        ok = top_id in expected
        correct += ok
        top2 = " | ".join(f"{PRODUCTS[pid][:38]} ({score:.2f})" for score, pid in ranked[:2])
        print(f"{query:<24}{'✅' if ok else '❌':<6}{top2}")

    print("-" * 110)
    print(f"Первым правильный товар: {correct} из {len(QUERIES)}")


if __name__ == "__main__":
    main()