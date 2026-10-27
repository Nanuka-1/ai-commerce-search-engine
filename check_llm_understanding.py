"""
U2.1 (12.10): живой замер — понимает ли ИИ «трудные» сообщения из стресс-тестов. В базу НЕ пишет, чат НЕ меняет.
Тратит ~1 обращение к LLM на фразу (~20 из 500/день). Нужно в .env: LLM_ENABLED=true, LLM_MODELS=...
Запуск: python check_llm_understanding.py
"""
import time

from app.services.llm_understanding_service import understand

# (сообщение, прошлый поиск клиента или None)
MESSAGES = [
    ("rogor xar ?", None),
    ("gamarjoba", None),
    ("კარგი მადლობა", None),
    ("vin xar?", None),
    ("asdf", None),
    ("კარგი", None),
    ("ეს რა ღირს?", None),
    ("მინდა საჩუქარი მეგობრისთვის, 100 ლარამდე", None),
    ("bichistvis minda fexsacmeli 33 zoma", None),
    ("ქალის სარბენი ფეხსაცმელი ფასდაკლებით 38", None),
    ("nike air max 42 cheaper than 300", None),
    ("ზამთარში სირბილისთვის რა მირჩევთ?", None),
    ("ხო და მაგალითად ეს ბოლო მოდელი", "სარბენი ფეხსაცმელი 42"),
    ("ხო და ეს ბოლო მოდელი რომელ ფილიალში არის მარაგში", "სარბენი ფეხსაცმელი 42"),
    ("rogor shevukveto?", None),
    ("mitana ramden xanshi?", None),
    ("are you a robot?", None),
    ("what can you do?", None),
]
PAUSE_SECONDS = 4.5      # лимит free: 15 запросов в минуту


def main():
    understood = 0
    for index, (message, previous) in enumerate(MESSAGES):
        if index:
            time.sleep(PAUSE_SECONDS)
        response = understand(message, previous)
        result = response["result"]
        print("=" * 110)
        print(f"СООБЩЕНИЕ: {message}" + (f"   (прошлый поиск: {previous})" if previous else ""))
        if result is None:
            print(f"  НЕ ПОНЯЛ: ошибки {response['errors']}")
            print(f"  ответ ИИ: {response['raw']}")
            continue
        understood += 1
        params = {key: result[key] for key in ("gender", "size", "brand", "max_price", "store_topic")
                  if result[key] is not None}
        flags = [key for key in ("discount_only", "gift", "refers_to_previous") if result[key]]
        print(f"  намерение: {result['intent']}   язык: {result['language']}")
        if result["query"]:
            print(f"  запрос для поиска: {result['query']}")
        if params or flags:
            print(f"  параметры: {params} {flags if flags else ''}")
        if result["reply"]:
            print(f"  ответ клиенту: {result['reply']}")
        if result["intent"] == "small_talk" and not result["reply"]:
            print(f"  ответ ОТКЛОНЁН барьером: {result['reply_rejected']}")
        print(f"  модель {response['model']}, {response['ms']} мс")
    print("=" * 110)
    print(f"Разобрано: {understood} из {len(MESSAGES)}")


if __name__ == "__main__":
    main()