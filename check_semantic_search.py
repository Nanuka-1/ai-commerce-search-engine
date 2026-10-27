"""
Проверка смыслового поиска на настоящем каталоге (шаг 3.5d). В базу НЕ пишет.

Для каждого запроса:
  - что поняли правила (размер, бренд, пол) — это фильтры;
  - топ-5 СМЫСЛОВОГО поиска (с близостью 0..1);
  - топ-3 ТОЧНОГО поиска (как сейчас в чате) — для сравнения.

Тратит 1 обращение к Gemini на запрос (~12 всего).
Запуск: Run в PyCharm (корень проекта).
"""
from sqlalchemy import text

from app.db.session import SessionLocal
from app.repositories.product_repository import size_variants
from app.services import cache_service
from app.services.product_service import search_products
from app.services.query_parser_service import extract_brand_from_query
from app.services.search_decision_service import apply_search_decision
from app.services.search_preparation_service import prepare_search
from app.services.search_request_builder import build_search_request
from app.services.semantic_search_service import semantic_search

QUERIES = [
    # смысловые
    "warm jacket M",
    "ზამთრის ქურთუკი M",
    "beach slippers 42",
    "სარბენი ფეხსაცმელი 42",
    "running shoes 42",
    "something for the gym L",
    "football boots 42",
    "women hoodie S",
    "kids shoes 30",
    "swimming",
    # точные — смысловой не должен терять точность
    "nike 42",
    "pegasus 42",
]


def names_by_page(db, pages: list[str]) -> dict:
    if not pages:
        return {}
    rows = db.execute(text("""
        SELECT DISTINCT ON (split_part(product_url, '?', 1))
               split_part(product_url, '?', 1) AS page, name
        FROM products
        WHERE split_part(product_url, '?', 1) = ANY(:pages)
        ORDER BY split_part(product_url, '?', 1), id
    """), {"pages": pages})
    return {row.page: row.name for row in rows}


def keyword_top(db, query: str, k: int = 3) -> list[str]:
    cache_service.clear()
    request = build_search_request(message=query, limit=k, offset=0)
    context = apply_search_decision(search_products(db, request), request)
    items = list(context.items or [])[:k]
    return [(item.get("name") if isinstance(item, dict) else item.name) or "?" for item in items]


def main():
    db = SessionLocal()
    for query in QUERIES:
        request = build_search_request(message=query, limit=10, offset=0)
        preparation = prepare_search(request)
        brand = request.brand or extract_brand_from_query(preparation.normalized_query)
        sizes = size_variants(request.size) if request.size else None
        category = preparation.category

        found = semantic_search(db, query, size_values=sizes, brand=brand, category=category, limit=5)
        names = names_by_page(db, [page for page, _ in found])

        print("=" * 120)
        print(f"ЗАПРОС: {query}    | правила: размер={request.size} бренд={brand} пол/категория={category}")
        print("  СМЫСЛОВОЙ:")
        if not found:
            print("    (ничего)")
        for page, similarity in found:
            print(f"    {similarity:.2f}  {names.get(page, page)[:90]}")
        print("  ТОЧНЫЙ (сейчас в чате):")
        for name in keyword_top(db, query) or ["(ничего)"]:
            print(f"          {name[:90]}")

    db.close()


if __name__ == "__main__":
    main()