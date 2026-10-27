"""
Замер для нижней планки смыслового поиска (09.10). В базу НЕ пишет.

Смысловой поиск ВСЕГДА находит «ближайшее», даже для бессмыслицы ("მოგესალმებით" → кепки, 0.625).
Сравниваем лучшее сходство (top-1) для осмысленных запросов и для мусора — ищем планку между ними.
Тратит ~14 обращений к Gemini (смысловой поиск, лимит 1 000/день).
Запуск: Run в PyCharm (корень проекта).
"""
from app.db.session import SessionLocal
from app.services.semantic_search_service import semantic_search

MEANINGFUL = [
    "beach slippers", "swimming", "something for the gym", "warm jacket", "football boots",
    "running shoes", "ზამთრის ქურთუკი", "სარბენი ფეხსაცმელი",
]
JUNK = [
    "მოგესალმებით", "როგორ ხარ", "კარგი", "test", "asdf", "what time is it",
    # из стресс-теста 09.10 (п.71)
    "rogor xar ?", "gamarjoba", "კარგი მადლობა", "ეს რა ღირს?",
]


def top(db, query):
    found = semantic_search(db, query, limit=3)
    return [round(similarity, 3) for _, similarity in found]


def main():
    db = SessionLocal()
    for title, queries in (("ОСМЫСЛЕННЫЕ", MEANINGFUL), ("МУСОР", JUNK)):
        print(f"\n{title}")
        for query in queries:
            print(f"  {query:<26} top-3: {top(db, query)}")
    db.close()


if __name__ == "__main__":
    main()