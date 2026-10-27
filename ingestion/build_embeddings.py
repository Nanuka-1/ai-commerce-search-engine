"""
Загрузка каталога в смысловой поиск (шаг 3.5c).

Для каждой активной модели (страницы сайта) собирает текст карточки, получает его точку
у Gemini и сохраняет в таблицу product_embeddings (Neon, pgvector).

Экономия бесплатного лимита Gemini (1 000 ТЕКСТОВ в день, считается каждый текст, не пачка):
  1. Одинаковые тексты считаются ОДИН раз (замер 06.10: 9 081 модель = 3 143 разных текста).
     Точка выдаётся всем страницам с этим текстом.
  2. Если такой текст уже посчитан раньше (есть в таблице) — копируем точку в базе, Gemini не нужен.
  3. Дневной бюджет DAILY_BUDGET: скрипт сам останавливается, оставляя запас на запросы клиентов.
     Сначала считаются самые частые тексты — они покрывают больше всего моделей.
  4. Пропуск по отпечатку (text_hash + модель): неизменённое не пересчитывается.

Прерывать можно в любой момент: каждая пачка сохраняется сразу, следующий запуск продолжит.
Запуск: Run (раз в день, пока каталог не загружен; потом — после каждого прогона скрапера).
"""
import time
from collections import defaultdict

from sqlalchemy import text

from app.db.models import Product
from app.db.session import SessionLocal
from app.services.embedding_client import EMBEDDING_MODEL, DailyQuotaExceeded, embed_documents
from app.services.embedding_text_service import build_embedding_text, text_hash

BATCH_SIZE = 100              # текстов в одном запросе к Gemini
PAUSE_BETWEEN_BATCHES = 30    # грузинский текст "тяжёлый" в токенах: 2 пачки/мин упирались в 30K TPM
DAILY_BUDGET = 800            # текстов за запуск; ~200 из 1 000/день остаются на запросы клиентов


def page_of(product_url: str) -> str:
    return (product_url or "").split("?")[0]


def pick_page_cards(products) -> dict:
    """Одна карточка на страницу: представитель — вариант с наименьшим id (стабильно между прогонами)."""
    cards = {}
    for product in sorted(products, key=lambda p: p.id):
        cards.setdefault(page_of(product.product_url), product)
    return cards


def select_pages_to_embed(texts_by_page: dict, saved: dict, model: str) -> list[str]:
    """Страницы, которым нужна новая точка: нет в таблице, текст изменился или другая модель Gemini.
    saved: {page_url: (text_hash, model)}"""
    return [
        page for page, page_text in texts_by_page.items()
        if saved.get(page) != (text_hash(page_text), model)
    ]


def plan_embedding(texts_by_page: dict, saved: dict, model: str, budget: int):
    """Что делать в этом запуске.
    Возвращает:
      copy_pages   — {page: hash}: точка с таким текстом уже есть в таблице → копируем в базе (бесплатно)
      new_groups   — [(hash, [pages])]: тексты для Gemini, самые частые первыми, не больше budget
      postponed    — сколько разных текстов отложено на следующий запуск (бюджет кончился)
    """
    known_hashes = {h for h, m in saved.values() if m == model}
    copy_pages = {}
    groups = defaultdict(list)
    for page in select_pages_to_embed(texts_by_page, saved, model):
        page_hash = text_hash(texts_by_page[page])
        if page_hash in known_hashes:
            copy_pages[page] = page_hash
        else:
            groups[page_hash].append(page)

    ordered = sorted(groups.items(), key=lambda item: len(item[1]), reverse=True)
    return copy_pages, ordered[:budget], max(0, len(ordered) - budget)


def to_vector_literal(vector: list[float]) -> str:
    """Формат pgvector: '[0.1,0.2,...]'"""
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"


UPSERT_SQL = text("""
    INSERT INTO product_embeddings (page_url, text_hash, model, embedding, updated_at)
    VALUES (:page_url, :text_hash, :model, CAST(:embedding AS vector), now())
    ON CONFLICT (page_url) DO UPDATE
       SET text_hash = EXCLUDED.text_hash, model = EXCLUDED.model,
           embedding = EXCLUDED.embedding, updated_at = now()
""")

COPY_SQL = text("""
    INSERT INTO product_embeddings (page_url, text_hash, model, embedding, updated_at)
    SELECT :page_url, :text_hash, :model, embedding, now()
    FROM product_embeddings
    WHERE text_hash = :text_hash AND model = :model
    LIMIT 1
    ON CONFLICT (page_url) DO UPDATE
       SET text_hash = EXCLUDED.text_hash, model = EXCLUDED.model,
           embedding = EXCLUDED.embedding, updated_at = now()
""")


def main(budget: int = DAILY_BUDGET):
    db = SessionLocal()
    started = time.perf_counter()

    products = db.query(Product).filter(Product.is_active.is_(True)).all()
    cards = pick_page_cards(products)
    texts_by_page = {page: build_embedding_text(card) for page, card in cards.items()}
    print(f"Активных моделей (страниц): {len(cards)}, разных текстов: {len(set(texts_by_page.values()))}")

    saved = {row.page_url: (row.text_hash, row.model)
             for row in db.execute(text("SELECT page_url, text_hash, model FROM product_embeddings"))}

    stale = [page for page in saved if page not in texts_by_page]
    if stale:
        db.execute(text("DELETE FROM product_embeddings WHERE page_url = ANY(:pages)"), {"pages": stale})
        db.commit()
        print(f"Удалено точек снятых моделей: {len(stale)}")

    copy_pages, new_groups, postponed = plan_embedding(texts_by_page, saved, EMBEDDING_MODEL, budget)

    if copy_pages:
        db.execute(COPY_SQL, [
            {"page_url": page, "text_hash": page_hash, "model": EMBEDDING_MODEL}
            for page, page_hash in copy_pages.items()
        ])
        db.commit()
        print(f"Скопировано готовых точек (тот же текст, без Gemini): {len(copy_pages)}")

    pages_in_new = sum(len(pages) for _, pages in new_groups)
    print(f"К Gemini: {len(new_groups)} текстов → покроют {pages_in_new} моделей. Отложено текстов: {postponed}")

    done_texts = 0
    done_pages = 0
    quota_hit = False
    for start in range(0, len(new_groups), BATCH_SIZE):
        batch = new_groups[start:start + BATCH_SIZE]
        first_pages = [pages[0] for _, pages in batch]
        try:
            vectors = embed_documents([texts_by_page[page] for page in first_pages])
        except DailyQuotaExceeded:
            quota_hit = True   # всё сделанное уже сохранено (commit после каждой пачки)
            print("\nДневной лимит Gemini исчерпан — останавливаюсь.")
            break
        rows = [
            {"page_url": page, "text_hash": page_hash, "model": EMBEDDING_MODEL,
             "embedding": to_vector_literal(vector)}
            for (page_hash, pages), vector in zip(batch, vectors)
            for page in pages
        ]
        db.execute(UPSERT_SQL, rows)
        db.commit()   # после каждой пачки: обрыв не теряет сделанное
        done_texts += len(batch)
        done_pages += len(rows)
        print(f"…текстов {done_texts} из {len(new_groups)} (моделей покрыто: {done_pages})")
        if start + BATCH_SIZE < len(new_groups):
            time.sleep(PAUSE_BETWEEN_BATCHES)

    total = db.execute(text("SELECT COUNT(*) FROM product_embeddings")).scalar()
    db.close()
    print(f"\nГотово за {time.perf_counter() - started:.0f} с. Точек в таблице: {total} из {len(cards)}")
    remaining = postponed + len(new_groups) - done_texts
    if remaining:
        reason = "лимит Gemini исчерпан раньше бюджета" if quota_hit else "дневной бюджет"
        print(f"Осталось {remaining} разных текстов — запустите завтра ({reason}).")


if __name__ == "__main__":
    main()