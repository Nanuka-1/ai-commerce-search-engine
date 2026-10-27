"""26.10: замер — какую похожесть смысловой поиск даёт бессмыслице и настоящим запросам.
Живьём: «ватлдвлвдыа» (новый посетитель, ИИ не успел) → 5 женских топов Adidas, хотя планка SEMANTIC_FLOOR = 0.62.
Запуск из корня проекта:  python measure_semantic_floor.py
Нужны DATABASE_URL и ключ Gemini в .env (как для приложения). Ничего не меняет в базе — только читает."""
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from sqlalchemy.orm import Session

from app.db.session import engine
from app.services.hybrid_search_service import SEMANTIC_FLOOR, SEMANTIC_MARGIN, filter_semantic
from app.services.semantic_search_service import semantic_search

GIBBERISH = ["ватлдвлвдыа", "аичичи", "БРОВЛДПОДЫЛЫВ", "asdfgh", "qwzxkj", "ქწერტ", "დჯვდკლვჯლვ"]
REAL = ["swimming", "warm jacket", "running shoes", "yoga", "საცურაო", "ბურთი", "ზამთრის ქურთუკი",
        "კალათბურთი", "backpack", "tennis"]


def show(group: str, queries: list[str], db) -> None:
    print(f"\n=== {group} ===")
    print(f"{'запрос':<20} {'лучший':>7} {'5-й':>7} {'после планки':>13}   топ-3 страницы")
    for query in queries:
        results = semantic_search(db, query, size_values=None, brand=None, category=None, limit=20)
        scores = sorted((similarity for _, similarity in results), reverse=True)
        kept = filter_semantic(results)
        best = f"{scores[0]:.3f}" if scores else "-"
        fifth = f"{scores[4]:.3f}" if len(scores) >= 5 else "-"
        top = ", ".join(page.rsplit("/", 1)[-1][:28] for page, _ in
                        sorted(results, key=lambda pair: pair[1], reverse=True)[:3])
        print(f"{query:<20} {best:>7} {fifth:>7} {len(kept):>13}   {top}")


if __name__ == "__main__":
    print(f"Сейчас: SEMANTIC_FLOOR = {SEMANTIC_FLOOR}, SEMANTIC_MARGIN = {SEMANTIC_MARGIN}")
    with Session(engine) as db:
        show("БЕССМЫСЛИЦА (должно остаться 0)", GIBBERISH, db)
        show("НАСТОЯЩИЕ (должно остаться > 0)", REAL, db)