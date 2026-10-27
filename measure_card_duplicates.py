"""
Замер перед шагом 3.3: сколько в выдаче повторов одной и той же модели (страницы).

Тот же поиск, что у чата и eval_search.py (без сессий/логов, в БД не пишет).
Для каждого запроса берём первые TOP товаров и считаем, сколько среди них разных страниц
(product_url без ?size=...). Если страниц меньше, чем товаров, — клиент видит повторы.

Запуск: Run в PyCharm (корень проекта).
"""
from collections import Counter

from app.db.models import Product
from app.db.session import SessionLocal
from app.services import cache_service
from app.services.product_service import search_products
from app.services.search_decision_service import apply_search_decision
from app.services.search_request_builder import build_search_request
from eval_search import _field

TOP = 10

QUERIES = [
    # без размера
    "pegasus", "nike", "adidas samba", "crocs", "classic clog",
    "adidas hoodie", "ქალის ჯემპრი", "running shoes",
    # с размером
    "nike 42", "crocs 42", "adidas hoodie M", "ქალის ჯემპრი S",
]


def load_rows(db, items) -> list:
    # полные строки products по SKU (поиск отдаёт урезанные словари), порядок сохраняем
    skus = [_field(item, "sku") for item in items]
    rows = {row.sku: row for row in db.query(Product).filter(Product.sku.in_(skus)).all()}
    return [rows.get(sku, item) for sku, item in zip(skus, items)]


def page_of(item) -> str:
    return (_field(item, "product_url") or "").split("?")[0]


def main():
    db = SessionLocal()
    print(f"{'запрос':<26}{'режим':<14}{'товаров':>8}{'страниц':>9}  самая частая страница")
    print("-" * 110)
    for query in QUERIES:
        cache_service.clear()
        request = build_search_request(message=query, limit=TOP, offset=0)
        context = apply_search_decision(search_products(db, request), request)
        items = load_rows(db, list(context.items or [])[:TOP])

        pages = Counter(page_of(item) for item in items)
        top_page, top_count = pages.most_common(1)[0] if pages else ("-", 0)
        print(f"{query[:25]:<26}{str(context.result_mode)[:13]:<14}{len(items):>8}{len(pages):>9}"
              f"  {top_count}× {top_page.rsplit('/', 1)[-1][:50]}")
    db.close()


if __name__ == "__main__":
    main()