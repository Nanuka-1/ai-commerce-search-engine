"""
Смысловой поиск по запросу клиента (шаг 3.5d). Только Postgres (pgvector).

  запрос → Gemini → точка запроса (1 обращение)
         → среди моделей, которые РАЗРЕШИЛИ ПРАВИЛА (в продаже, размер, бренд, пол),
           найти ближайшие по смыслу точки из product_embeddings.

Правила (фильтры) — твёрдые: то, что клиент назвал точно, не обсуждается.
Смысл ищется только внутри разрешённого. Товары не выбирает Gemini — их выбирает база.

Пока НЕ подключён к чату: используется проверочным скриптом check_semantic_search.py.
В чат войдёт на шаге 3.6 (слияние с точным поиском).
"""
from sqlalchemy import text

from app.services.embedding_client import embed_query

# Для взрослых добавляем Unisex (как category_condition в product_repository); детям — нет.
CATEGORIES_WITH_UNISEX = {"მამაკაც", "ქალ"}


def build_semantic_sql(size_values: list[str] | None, brand: str | None,
                       category: str | None, limit: int):
    """SQL и параметры: фильтры добавляются только если правило что-то поняло из запроса."""
    conditions = ["p.is_active"]
    params = {"limit": limit}

    if size_values:
        conditions.append("p.size = ANY(:sizes)")
        params["sizes"] = list(size_values)
    if brand:
        conditions.append("lower(p.brand) = :brand")
        params["brand"] = brand.lower()
    if category:
        category_sql = "p.category_slug ILIKE :category_like"
        if category in CATEGORIES_WITH_UNISEX:
            category_sql = f"({category_sql} OR p.category_slug ILIKE 'Unisex%')"
        conditions.append(category_sql)
        params["category_like"] = f"%{category}%"

    sql = f"""
        WITH allowed AS (
            SELECT DISTINCT split_part(p.product_url, '?', 1) AS page
            FROM products p
            WHERE {" AND ".join(conditions)}
        )
        SELECT e.page_url,
               1 - (e.embedding <=> CAST(:query_vector AS vector)) AS similarity
        FROM product_embeddings e
        JOIN allowed a ON a.page = e.page_url
        ORDER BY e.embedding <=> CAST(:query_vector AS vector)
        LIMIT :limit
    """
    return sql, params


def to_vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"


def semantic_search(db, query_text: str, size_values=None, brand=None, category=None,
                    limit: int = 10, query_vector: list[float] | None = None) -> list[tuple[str, float]]:
    """[(page_url, сходство 0..1), ...] — ближайшие по смыслу модели среди разрешённых правилами."""
    if query_vector is None:
        query_vector = embed_query(query_text)
    sql, params = build_semantic_sql(size_values, brand, category, limit)
    params["query_vector"] = to_vector_literal(query_vector)
    return [(row.page_url, float(row.similarity)) for row in db.execute(text(sql), params)]