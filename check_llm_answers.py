"""
Шаг 3.7d: живая проверка ответов LLM на настоящем каталоге. В базу НЕ пишет.

Тот же путь, что у чата: поиск → решение → шаблон (response_builder) → enhance_response (LLM).
Для каждого запроса печатает: ШАБЛОН | LLM-текст | модель | время | причина, если шаблон.

Тратит ~1 обращение к LLM (из 500/день) и ≤1 к смысловому поиску на запрос (~10 всего).
Запуск: Run в PyCharm (корень проекта). Нужно в .env: LLM_ENABLED=true, LLM_MODELS=...
"""
import textwrap

from app.db.session import SessionLocal
from app.services import cache_service
from app.services.ai_response_service import enhance_response
from app.services.product_service import search_products
from app.services.response_builder import build_response
from app.services.search_decision_service import apply_search_decision
from app.services.search_request_builder import build_search_request

# (запрос, язык страницы сайта) — латиница получает язык страницы, грузинский текст всегда ka
QUERIES = [
    ("nike 42", "ka"),
    ("nike 42", "en"),
    ("running shoes 42", "en"),
    ("სარბენი ფეხსაცმელი 42", "ka"),
    ("warm jacket M", "en"),
    ("ზამთრის ქურთუკი M", "ka"),
    ("ქალის ჯემპრი S", "ka"),
    ("ბავშვის ბოტასი 30", "ka"),
    ("adidas samba 40", "ka"),
    ("crocs 42", "en"),
    ("pegasus", "ka"),            # вопрос о размере → LLM не нужен (шаблон)
]


def show(label: str, text: str | None):
    wrapped = textwrap.fill(text or "—", width=110, subsequent_indent=" " * 12)
    print(f"  {label:<9} {wrapped}")


def main():
    db = SessionLocal()
    used = rejected = 0
    for query, locale in QUERIES:
        cache_service.clear()
        request = build_search_request(message=query, limit=5, offset=0)
        context = apply_search_decision(search_products(db, request), request)
        base = build_response(context, user_id="llm-check", response_type="product_search", locale=locale)
        response = enhance_response(base, context)
        meta = response.get("meta", {})

        print("=" * 125)
        print(f"ЗАПРОС: {query}   (страница {locale}, найдено {context.total_count}, режим {context.result_mode})")
        show("ШАБЛОН:", response.get("template_message", base.get("message")))
        if meta.get("ai_used"):
            used += 1
            show("LLM:", response["message"])
            print(f"  {'':<9} модель {meta.get('ai_model')}, {meta.get('ai_response_time_ms')} мс")
        else:
            reason = meta.get("ai_fallback_reason")
            rejected += str(reason).startswith("rejected")
            print(f"  {'шаблон:':<9} причина {reason}, модель {meta.get('ai_model')}, {meta.get('ai_response_time_ms')} мс")
            if meta.get("ai_rejected_text"):
                show("ОТКЛОНЁН:", meta["ai_rejected_text"])
    db.close()
    print("=" * 125)
    print(f"LLM-текст показан: {used} из {len(QUERIES)}; отклонено проверкой: {rejected}")


if __name__ == "__main__":
    main()