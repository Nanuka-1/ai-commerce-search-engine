"""
Golden set: оценка качества поиска на наборе эталонных запросов.

Вызывает тот же поиск, что и чат (build_search_request -> search_products -> apply_search_decision),
но БЕЗ сессий, задач и логов — в базу ничего не пишет, только читает products.
ИИ-понимание сюда НЕ входит (его меряет check_llm_understanding.py): здесь качество самого поискового движка.

Каждый случай проверяет то, что видит клиент:
  - что понял поиск (режим ответа: need_size / found и т.п.),
  - что товары топ-5 подходят под жёсткие условия запроса (бренд, размер, пол, цвет, тип, бюджет, скидка),
  - что в топ-5 есть нужная модель (по слову в названии).

Ожидания описаны свойствами, а не конкретными SKU: каталог меняется каждый день,
а "nike 42 -> только Nike в размере 42" остаётся верным всегда.

20.10 (этап 2): две оценки вместо одной —
  строго  = ВСЕ товары топ-5 подходят (качество всей выдачи) — как раньше;
  hit@5   = ХОТЯ БЫ ОДИН товар топ-5 подходит (клиент увидит то, что искал).
Бюджет и скидка разбираются как в чате (deal_rules_service.parse_deal_filters).
Новые билеты (stage "2") — реальные формулировки из search_events; stage "3" — функции этапа 3 (новинки),
сейчас падают — это и есть исходная точка (baseline).

Колонка "источник": откуда пришли товары топ-5 — т = точный поиск, с = смысловой, о = оба;
  "выкл" = гибрид не сработал (SEMANTIC_SEARCH_ENABLED не true, ошибка/лимит Gemini, фильтры бюджета/скидки).

Запуск: Run в PyCharm (корень проекта) или python eval_search.py
"""
from app.db.models import Product
from app.db.session import SessionLocal
from app.repositories.product_repository import size_variants
from app.services import cache_service
from app.services.deal_rules_service import parse_deal_filters
from app.services.product_service import search_products
from app.services.search_decision_service import apply_search_decision
from app.services.search_request_builder import build_search_request

TOP_K = 5
SPORT_MIN = 3   # из TOP_K

MEN = ["მამაკაც", "Unisex"]
WOMEN = ["ქალ", "Unisex"]
KIDS = ["ბავშვ"]

CASES = [
    # --- бренд + размер ---
    {"query": "nike 42", "brand": "Nike", "size": "42", "stage": "base"},
    {"query": "nike 42.5", "brand": "Nike", "size": "42.5", "stage": "base"},
    {"query": "adidas 40", "brand": "Adidas", "size": "40", "stage": "base"},
    {"query": "puma 41", "brand": "Puma", "size": "41", "stage": "base"},
    {"query": "reebok 43", "brand": "Reebok", "size": "43", "stage": "base"},
    {"query": "crocs 42", "brand": "Crocs", "size": "42", "stage": "3.2"},
    {"query": "under armour shorts L", "brand": "Under Armour", "size": "L", "stage": "base"},
    {"query": "adidas hoodie M", "brand": "Adidas", "size": "M", "stage": "base"},

    # --- модель ---
    {"query": "pegasus", "mode": "need_size", "stage": "base"},
    {"query": "pegasus 41", "mode": "need_size", "stage": "base"},          # 41 — версия, не размер
    {"query": "pegasus 42", "size": "42", "name": "pegasus", "stage": "base"},  # 07.10: версии 42 нет → размер
    {"query": "air force 1 44", "brand": "Nike", "size": "44", "name": "air force", "stage": "base"},
    {"query": "nike air max 90 42", "brand": "Nike", "size": "42", "name": "air max", "stage": "base"},
    {"query": "samba 40", "size": "40", "name": "samba", "stage": "base"},
    {"query": "adidas samba 40", "brand": "Adidas", "size": "40", "name": "samba", "stage": "base"},
    {"query": "classic clog 42", "size": "42", "name": "classic clog", "stage": "base"},
    {"query": "adilette 42", "size": "42", "name": "adilette", "stage": "base"},

    # --- категория / пол (грузинский) ---
    {"query": "მამაკაცის სპორტული ფეხსაცმელი 43", "size": "43", "category": MEN, "stage": "base"},
    {"query": "ქალის ჯემპრი S", "size": "S", "category": WOMEN, "stage": "base"},
    {"query": "ბავშვის ბოტასი 30", "size": "30", "category": KIDS, "stage": "base"},
    {"query": "ქალის სპორტული ფეხსაცმელი 38", "size": "38", "category": WOMEN, "stage": "base"},

    # --- цвет ---
    {"query": "puma black 41", "brand": "Puma", "size": "41", "color": "black", "stage": "base"},
    {"query": "nike white 42", "brand": "Nike", "size": "42", "color": "white", "stage": "base"},
    {"query": "შავი nike 42", "brand": "Nike", "size": "42", "color": "black", "stage": "base"},

    # --- артикул ---
    # 06.10 (3.6b): клиент ищет ОДИН товар — лишние карточки рядом = ошибка
    {"query": "31241503", "name": "puma", "max_items": 1, "stage": "base"},

    # --- бренд по-грузински ---
    {"query": "ნაიკი 42", "brand": "Nike", "size": "42", "stage": "3.2"},
    {"query": "ადიდასი 40", "brand": "Adidas", "size": "40", "stage": "3.2"},

    # --- опечатки (fuzzy) ---
    {"query": "nkie 42", "brand": "Nike", "size": "42", "stage": "3.4"},
    {"query": "adidsa samba 40", "brand": "Adidas", "size": "40", "name": "samba", "stage": "3.4"},
    {"query": "pegasos", "mode": "need_size", "stage": "3.4"},

    # --- смысловые (vector) — 04.10 ужесточены: проверяем не только размер, но и ЧТО показали ---
    {"query": "running shoes 42", "size": "42", "product_type": "footwear", "sport": "running", "stage": "3.5"},
    {"query": "სარბენი ფეხსაცმელი 42", "size": "42", "product_type": "footwear", "sport": "running", "stage": "3.5"},
    {"query": "warm jacket M", "size": "M", "name_any": ["ქურთუკ", "jacket"], "stage": "3.5"},

    # ===== 20.10 (этап 2): реальные формулировки из search_events =====
    # --- дети («ბიჭის» в названиях каталога нет — п.119) ---
    {"query": "ბავშვის ბიჭის ფეხსაცმელი 36", "size": "36", "category": KIDS, "product_type": "footwear",
     "stage": "2"},
    {"query": "ბიჭის ფეხსაცმელი 36", "size": "36", "category": KIDS, "product_type": "footwear", "stage": "2"},
    {"query": "ბავშვის ფეხსაცმელი 33", "size": "33", "category": KIDS, "product_type": "footwear", "stage": "2"},
    {"query": "kids 30", "size": "30", "category": KIDS, "stage": "2"},

    # --- пол + тип ---
    {"query": "ქალის სარბენი ფეხსაცმელი 38", "size": "38", "category": WOMEN, "product_type": "footwear",
     "sport": "running", "stage": "2"},
    {"query": "კაცის სარბენი 42", "size": "42", "category": MEN, "product_type": "footwear", "sport": "running",
     "stage": "2"},
    {"query": "ქალის ფეხსაცმელი 36 ზომა", "size": "36", "category": WOMEN, "product_type": "footwear",
     "stage": "2"},
    {"query": "ქალის ქურთუკი M", "size": "M", "category": WOMEN, "name_any": ["ქურთუკ"], "stage": "2"},
    {"query": "მამაკაცის შორტი L", "size": "L", "category": MEN, "name_any": ["შორტ"], "stage": "2"},
    {"query": "ქალის შარვალი M", "size": "M", "category": WOMEN, "name_any": ["შარვალ"], "stage": "2"},
    {"query": "მამაკაცის სარბენი ბოტასი 45 ზომა", "size": "45", "category": MEN, "product_type": "footwear",
     "stage": "2"},

    # --- бренд / модель ---
    {"query": "ქალის სარბენი ფეხსაცმელი puma 38", "brand": "Puma", "size": "38", "category": WOMEN,
     "stage": "2"},
    {"query": "ნაიკის მოდელი ფეხსაცმელი მინდა 36 ზომა ქალისთვის", "brand": "Nike", "size": "36",
     "category": WOMEN, "stage": "2"},
    {"query": "adidas samba 38", "brand": "Adidas", "size": "38", "name": "samba", "stage": "2"},
    {"query": "puma speedcat 38", "size": "38", "name": "speedcat", "stage": "2"},

    # --- бюджет / скидка (как в чате: parse_deal_filters) ---
    {"query": "ქალის სარბენი ფეხსაცმელი 150 ლარამდე", "category": WOMEN, "product_type": "footwear",
     "max_price": 150, "stage": "2"},
    {"query": "ბავშვის ფეხსაცმელი ფასდაკლებით", "category": KIDS, "discount": True, "stage": "2"},
    {"query": "nike 42 200 ლარამდე", "brand": "Nike", "size": "42", "max_price": 200, "stage": "2"},

    # --- этап 3: новинки (is_new ещё нет → сейчас падает, это baseline) ---
    {"query": "ახალი კოლექცია ქალის ფეხსაცმელი 36", "size": "36", "category": WOMEN, "is_new": True,
     "stage": "3"},
]


def _field(item, name):
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


SOURCE_LETTERS = {"keyword": "т", "semantic": "с", "both": "о"}


def source_summary(items) -> str:
    """Откуда пришли товары топ-5: 'т3 о2'. Метку source ставит гибрид (hybrid_search_service).
    Ни у одного товара нет метки -> гибрид не сработал -> 'выкл'. Пустая выдача -> '-'."""
    top = list(items or [])[:TOP_K]
    if not top:
        return "-"
    sources = [_field(item, "source") for item in top]
    if all(source is None for source in sources):
        return "выкл"
    counts = {}
    for source in sources:
        letter = SOURCE_LETTERS.get(source, "?")
        counts[letter] = counts.get(letter, 0) + 1
    return " ".join(f"{letter}{counts[letter]}" for letter in ("т", "с", "о", "?") if letter in counts)


def load_products(db, items) -> list:
    """Поиск отдаёт товары в разном виде (объекты / словари с частью полей).
    Для проверки берём настоящие строки из products по SKU — в том же порядке."""
    items = list(items or [])[:TOP_K]
    skus = [_field(item, "sku") for item in items]
    rows = {row.sku: row for row in db.query(Product).filter(Product.sku.in_(skus)).all()}
    return [rows.get(sku, item) for sku, item in zip(skus, items)]


def item_problems(case: dict, item) -> list[str]:
    """Проблемы ОДНОГО товара (пустой список = товар подходит клиенту)."""
    problems = []
    name = _field(item, "name") or ""
    allowed_sizes = size_variants(case["size"]) if case.get("size") else None

    if case.get("brand") and (_field(item, "brand") or "").lower() != case["brand"].lower():
        problems.append(f"чужой бренд: {name}")
    if allowed_sizes and _field(item, "size") not in allowed_sizes:
        problems.append(f"размер {_field(item, 'size')}: {name}")
    if case.get("category") and not any(root in (_field(item, "category_slug") or "")
                                        for root in case["category"]):
        problems.append(f"категория {(_field(item, 'category_slug') or '')[:20]}: {name}")
    # Цвет известен лишь у части товаров. Неизвестный цвет допустим; ошибка — только ДРУГОЙ известный цвет.
    item_color = _field(item, "color")
    if case.get("color") and item_color is not None and item_color != case["color"]:
        problems.append(f"цвет {item_color}: {name}")
    if case.get("product_type") and _field(item, "product_type") != case["product_type"]:
        problems.append(f"тип {_field(item, 'product_type')}: {name}")
    if case.get("name_any") and not any(word in name.lower() for word in case["name_any"]):
        problems.append(f"не тот товар: {name}")

    price = _field(item, "price")
    regular = _field(item, "regular_price")
    if case.get("max_price") and (price is None or price > case["max_price"]):
        problems.append(f"дороже {case['max_price']}: {price} {name}")
    if case.get("discount") and not (regular and price and regular > price):
        problems.append(f"без скидки: {name}")
    if case.get("is_new") and _field(item, "is_new") is not True:
        problems.append(f"не новинка: {name}")
    return problems


def evaluate_case(case: dict, result_mode, items: list) -> tuple[list[str], bool]:
    """20.10: (проблемы для строгой оценки, hit@5). Пустой список проблем = случай пройден строго."""
    top = items[:TOP_K]

    expected_mode = case.get("mode")
    if expected_mode:
        ok = result_mode == expected_mode
        return ([] if ok else [f"режим {result_mode}, ожидали {expected_mode}"]), ok

    if not top:
        return [f"пусто (режим {result_mode})"], False

    problems = []
    if case.get("max_items") and len(top) > case["max_items"]:
        problems.append(f"лишние товары: {len(top)} вместо {case['max_items']}")

    good_items = []
    for item in top:
        found = item_problems(case, item)
        problems.extend(found)
        if not found:
            good_items.append(item)

    if case.get("sport"):
        matching = sum(1 for i in top if _field(i, "sport_type") == case["sport"])
        if matching < min(SPORT_MIN, len(top)):
            problems.append(f"для '{case['sport']}' только {matching} из {len(top)}")

    if case.get("name") and not any(case["name"] in (_field(i, "name") or "").lower() for i in top):
        problems.append(f"нет '{case['name']}' в топ-{TOP_K}")

    # hit@5: хотя бы один товар подходит по всем условиям (и с нужной моделью, если она задана)
    if case.get("name"):
        good_items = [i for i in good_items if case["name"] in (_field(i, "name") or "").lower()]
    if case.get("sport"):
        good_items = [i for i in good_items if _field(i, "sport_type") == case["sport"]]
    return problems, bool(good_items)


def check_case(case: dict, result_mode, items: list) -> list[str]:
    """Строгая оценка, как раньше (список проблем) — её используют тесты tests/unit/test_eval_search.py."""
    return evaluate_case(case, result_mode, items)[0]


def build_request(query: str):
    """Как чат на пути правил: бюджет и скидка — фильтрами, в текст поиска идёт очищенная фраза."""
    deal = parse_deal_filters(query)
    request = build_search_request(message=deal.cleaned or query, limit=TOP_K, offset=0)
    updates = {}
    if deal.max_price or deal.discount_only or deal.new_only:
        updates.update(max_price=deal.max_price, discount_only=deal.discount_only, new_only=deal.new_only)
    if deal.prefer_discount and not deal.discount_only:
        updates["prefer_discount"] = True
    return request.model_copy(update=updates) if updates else request


def _understood(request) -> str:
    parts = []
    for attr in ("brand", "size", "color", "category", "model_hint", "max_price", "discount_only"):
        value = getattr(request, attr, None)
        if value:
            parts.append(f"{attr}={value}")
    return " ".join(parts) or "-"


def main():
    db = SessionLocal()
    strict_passed = hits = 0
    by_stage: dict[str, list[int]] = {}
    hybrid_off = 0

    print(f"{'запрос':<36}{'строго':<8}{'hit@5':<7}{'stage':<7}{'источник':<11}{'понял':<40}проблемы")
    print("-" * 160)
    for case in CASES:
        cache_service.clear()
        request = build_request(case["query"])
        context = search_products(db, request)
        context = apply_search_decision(context, request)

        # метку source читаем ДО load_products: строки из products её не содержат
        source = source_summary(context.items)
        hybrid_off += source == "выкл"

        problems, hit = evaluate_case(case, context.result_mode, load_products(db, context.items))
        ok = not problems
        strict_passed += ok
        hits += hit
        stage_stats = by_stage.setdefault(case["stage"], [0, 0, 0])
        stage_stats[0] += ok
        stage_stats[1] += hit
        stage_stats[2] += 1

        # Повторы одной проблемы (5 товаров с одним чужим размером) сворачиваем
        unique = list(dict.fromkeys(problems))[:3]
        print(f"{case['query'][:35]:<36}{'✅' if ok else '❌':<8}{'✅' if hit else '❌':<7}{case['stage']:<7}"
              f"{source:<11}{_understood(request)[:39]:<40}{'; '.join(unique)}")

    db.close()
    total = len(CASES)
    print("-" * 160)
    print(f"СТРОГО (все {TOP_K} подходят): {strict_passed} из {total} ({strict_passed / total * 100:.0f}%)")
    print(f"HIT@{TOP_K} (хотя бы 1 подходит): {hits} из {total} ({hits / total * 100:.0f}%)")
    for stage, (ok_count, hit_count, stage_total) in sorted(by_stage.items()):
        print(f"  stage {stage:<5} строго {ok_count}/{stage_total}   hit@{TOP_K} {hit_count}/{stage_total}")
    print(f"Гибрид не сработал (выкл): {hybrid_off} из {total} (need_size без товаров — '-')")


if __name__ == "__main__":
    main()