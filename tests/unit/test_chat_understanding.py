"""U2.2: чат + понимание ИИ. Gemini не вызываем — подменяем understand() готовым разбором."""
import pytest
from app.services import cache_service

from app.services import llm_client
from app.services.translations import translate
from app.use_cases import chat_use_case as module
from app.use_cases.chat_use_case import ChatUseCase

BASE = {
    "intent": "unclear", "language": "ka", "query": None, "gender": None, "size": None, "brand": None,
    "max_price": None, "discount_only": False, "gift": False, "store_topic": None,
    "refers_to_previous": False, "wants_other": False, "reply": None, "reply_rejected": None,
}


@pytest.fixture(autouse=True)
def clean_cache():
    # 22.10: карточка условий живёт в кэше — каждый тест начинает разговор с чистого листа
    cache_service.clear()


@pytest.fixture
def llm_on(monkeypatch):
    monkeypatch.setattr(llm_client, "is_enabled", lambda: True)


def fake_understanding(monkeypatch, **fields):
    calls = []

    def fake(message, previous_query=None, history=None):
        calls.append(message)
        fake.history = history
        result = None if fields.get("result_none") else {**BASE, **fields}
        return {"result": result, "model": "fake-model", "ms": 1.0, "raw": "", "errors": []}

    monkeypatch.setattr(module, "understand", fake)
    return calls


def run(message, locale="ka"):
    return ChatUseCase()._handle_understanding(None, "u1", message, locale, 5, 0, session=None, active_task=None)


def test_small_talk_gets_live_reply(llm_on, monkeypatch):
    fake_understanding(monkeypatch, intent="small_talk", reply="მადლობა, კარგად! რით დაგეხმაროთ? 🙂")
    response = run("rogor xar ?")
    assert response["type"] == "small_talk"
    assert response["message"] == "მადლობა, კარგად! რით დაგეხმაროთ? 🙂"
    assert response["meta"]["ai_used"] is True
    assert response["meta"]["understanding"] == "small_talk"


def test_small_talk_without_safe_reply_uses_template(llm_on, monkeypatch):
    fake_understanding(monkeypatch, intent="small_talk", reply=None)
    response = run("rogor xar ?")
    assert response["message"] == translate("small_talk", "ka")
    assert response["meta"]["ai_used"] is False


def test_store_question_answered_from_our_file(llm_on, monkeypatch):
    fake_understanding(monkeypatch, intent="store_question", store_topic="delivery")
    response = run("mitana ramden xanshi?")
    assert response["type"] == "store_info"
    assert response["data"]["topic"] == "delivery"


def test_product_search_goes_to_our_search_with_understood_query(llm_on, monkeypatch):
    fake_understanding(monkeypatch, intent="product_search", query="ბავშვის ფეხსაცმელი", size="33", gender="kids")
    searched = []
    monkeypatch.setattr(ChatUseCase, "_handle_product_search",
                        lambda self, db, user_id, message, *args, **kwargs: searched.append(message) or {"type": "product_search"})
    response = run("bichistvis minda fexsacmeli 33 zoma")
    assert searched == ["ბავშვის ფეხსაცმელი 33"]         # размер дописан к запросу
    assert response["meta"]["understood_query"] == "ბავშვის ფეხსაცმელი 33"


@pytest.mark.parametrize("fields, key", [
    ({"intent": "product_search", "gift": True}, "gift_suggestion"),
    ({"intent": "product_question", "store_topic": "stores"}, "product_stock_in_stores"),
    ({"intent": "product_question"}, "clarify_product"),
    ({"intent": "unclear"}, "unclear_request"),
])
def test_clarifying_answers(llm_on, monkeypatch, fields, key):
    fake_understanding(monkeypatch, **fields)
    response = run("ეს რა ღირს?")
    assert response["type"] == "clarify"
    assert response["message"] == translate(key, "ka")


def test_llm_unavailable_falls_back_to_old_path(llm_on, monkeypatch):
    fake_understanding(monkeypatch, result_none=True)
    assert run("rogor xar ?") is None


def test_rules_understood_no_llm_call(llm_on, monkeypatch):
    calls = fake_understanding(monkeypatch, intent="small_talk", reply="—")
    assert run("nike 42") is None              # бренд — правила поняли
    assert run("CW2288-111") is None           # артикул
    assert calls == []                          # ИИ не вызывали — лимит не тратим


def test_llm_disabled_no_call(monkeypatch):
    monkeypatch.setattr(llm_client, "is_enabled", lambda: False)
    calls = fake_understanding(monkeypatch, intent="small_talk", reply="—")
    assert run("rogor xar ?") is None
    assert calls == []


def test_template_answer_in_page_language_not_llm_guess(llm_on, monkeypatch):
    # 12.10: «asdf» на KA-странице → ИИ сказал language=en → ответ был по-английски
    fake_understanding(monkeypatch, intent="unclear", language="en")
    response = run("asdf", locale="ka")
    assert response["message"] == translate("unclear_request", "ka")


def test_budget_and_discount_passed_to_our_search(llm_on, monkeypatch):
    # U2.3: ИИ понял «до 100 лари» и «со скидкой» → фильтры уходят в НАШ поиск
    fake_understanding(monkeypatch, intent="product_search", query="ბავშვის ფეხსაცმელი",
                       max_price=100.0, discount_only=True)
    captured = {}
    monkeypatch.setattr(ChatUseCase, "_handle_product_search",
                        lambda self, db, user_id, message, *args, **kwargs:
                        captured.update(kwargs, message=message) or {"type": "product_search"})
    response = run("ბავშვის ფეხსაცმელი ფასდაკლებით 100 ლარამდე")
    assert captured["message"] == "ბავშვის ფეხსაცმელი"
    assert captured["max_price"] == 100.0 and captured["discount_only"] is True
    assert response["meta"]["discount_only"] is True


# --- А2 (12.10): «покажи скидки» без типа товара → подборка ---

DROP = {"name": "Nike მაისური", "brand": "Nike", "price": 99.0, "regular_price": None, "old_price": 222.0,
        "drop_percent": 55, "product_url": "https://topsport.ge/ka/product/f", "image_url": None}
DEAL = {"name": "Adidas ჯემპრი", "brand": "Adidas", "price": 140.0, "regular_price": 200.0,
        "discount_percent": 30, "product_url": "https://topsport.ge/ka/product/a", "image_url": None}


def _deals_setup(monkeypatch, fresh, top):
    # подборка живёт в promo_service.build_deals_response (её же зовёт кнопка виджета) — подменяем там
    from app.services import promo_service
    monkeypatch.setattr(promo_service, "load_config", lambda: {"min_drop_percent": 10, "min_discount_percent": 20,
                                                               "sale_url": {"ka": "https://topsport.ge/ka/products/sale"}})
    monkeypatch.setattr(promo_service, "select_fresh_drops",
                        lambda db, limit, min_drop: (fresh, "2026-10-09" if fresh else None))
    monkeypatch.setattr(promo_service, "select_auto_deals", lambda db, limit, min_discount: top)


def test_show_deals_fresh_drops_with_date(llm_on, monkeypatch):
    fake_understanding(monkeypatch, intent="product_search", discount_only=True)
    _deals_setup(monkeypatch, fresh=[DROP], top=[DEAL])
    response = run("ფასდაკლებები მაჩვენე")
    assert response["type"] == "deals"
    assert response["message"] == translate("deals_fresh", "ka").format(date="09.10")
    item = response["data"]["results"]["items"][0]
    assert item["regular_price"] == 222.0           # карточка: было 222 → стало 99
    assert response["data"]["results"]["site_search_url"] == "https://topsport.ge/ka/products/sale"


def test_show_deals_falls_back_to_top_discounts(llm_on, monkeypatch):
    fake_understanding(monkeypatch, intent="product_search", discount_only=True)
    _deals_setup(monkeypatch, fresh=[], top=[DEAL])
    response = run("ფასდაკლებები მაჩვენე")
    assert response["message"] == translate("deals_top", "ka")
    assert [i["name"] for i in response["data"]["results"]["items"]] == ["Adidas ჯემპრი"]


def test_show_deals_respects_budget(llm_on, monkeypatch):
    fake_understanding(monkeypatch, intent="product_search", discount_only=True, max_price=100.0)
    _deals_setup(monkeypatch, fresh=[], top=[DEAL])      # 140 ₾ > бюджета
    response = run("ფასდაკლებები 100 ლარამდე")
    assert response["data"]["results"]["items"] == []
    assert response["message"] == translate("deals_none", "ka")



def test_gender_from_understanding_added_to_query(llm_on, monkeypatch):
    # 12.10: «ბიჭის ზომა 36, 100 ლარის ფარგლებში» → ИИ: kids, но запрос без пола → нашлись женские кроссовки
    fake_understanding(monkeypatch, intent="product_search", query="ფეხსაცმელი", size="36", gender="kids",
                       max_price=100.0)
    searched = []
    monkeypatch.setattr(ChatUseCase, "_handle_product_search",
                        lambda self, db, user_id, message, *args, **kwargs: searched.append(message) or {"type": "product_search"})
    run("ბიჭის ზომა 36, 100 ლარის ფარგლებში შემარჩიეთ")
    assert searched == ["ბავშვის ფეხსაცმელი 36"]



def test_correction_in_conversation_goes_to_understanding(llm_on, monkeypatch):
    # 12.10: «თქვენ ქალის მოდელს მაჩვენებთ და მე ბიჭის მინდა» — в разговоре правила видели «ქალის» и искали женское
    calls = fake_understanding(monkeypatch, intent="product_search", query="ბავშვის ფეხსაცმელი", size="36",
                               gender="kids", max_price=100.0)
    captured = {}
    monkeypatch.setattr(ChatUseCase, "_handle_product_search",
                        lambda self, db, user_id, message, *args, **kwargs:
                        captured.update(kwargs, message=message) or {"type": "product_search"})
    history = ["ბიჭის ზომა 36, 100 ლარის ფარგლებში შემარჩიეთ"]
    ChatUseCase()._handle_understanding(None, "u1", "თქვენ ქალის მოდელს მაჩვენებთ და მე ბიჭის მინდა", "ka", 5, 0,
                                        session=None, active_task=None, history=history)
    assert calls == ["თქვენ ქალის მოდელს მაჩვენებთ და მე ბიჭის მინდა"]     # ИИ позвали, несмотря на «ქალის»
    assert module.understand.history == history                               # и передали прошлые сообщения
    assert captured["message"] == "ბავშვის ფეხსაცმელი 36" and captured["max_price"] == 100.0


def test_short_message_in_conversation_stays_with_rules(llm_on, monkeypatch):
    calls = fake_understanding(monkeypatch, intent="small_talk", reply="—")
    response = ChatUseCase()._handle_understanding(None, "u1", "ქალის ქურთუკი", "ka", 5, 0,
                                                   session=None, active_task=None, history=["nike 42"])
    assert response is None and calls == []                                   # 2 слова с полом — правила



# --- U2.5 (13.10): «другие / кроме этих» ---

from types import SimpleNamespace

from app.services import cache_service

PAGE_URL = "https://topsport.ge/ka/product/"


def test_wants_other_excludes_already_shown(llm_on, monkeypatch):
    cache_service.set("chat:shown:u1", [f"{PAGE_URL}a", f"{PAGE_URL}b"], ttl=60)
    fake_understanding(monkeypatch, intent="product_search", query="ბავშვის ფეხსაცმელი", size="36",
                       max_price=100.0, wants_other=True)
    captured = {}
    monkeypatch.setattr(ChatUseCase, "_handle_product_search",
                        lambda self, db, user_id, message, *args, **kwargs:
                        captured.update(kwargs) or {"type": "product_search"})
    run("ამ სამი მოდელის გარდა სხვა მოდელები არ არის?")
    assert captured["exclude_pages"] == [f"{PAGE_URL}a", f"{PAGE_URL}b"]
    assert captured["max_price"] == 100.0                     # условия прошлого запроса сохранены


def _search_stubs(monkeypatch, items):
    context = SimpleNamespace(items=list(items), total_count=len(items), result_mode="found", query="q")
    monkeypatch.setattr(module, "search_products", lambda db, request: context)
    monkeypatch.setattr(module, "apply_search_decision", lambda products, request: products)
    monkeypatch.setattr(module, "resolve_next_step", lambda mode: None)
    monkeypatch.setattr(module, "sync_search_task_after_result", lambda **kwargs: None)
    calls = []

    def fake_build(products, user_id, kind, locale, **kwargs):
        calls.append(kwargs)
        return {"type": kind, "message": "found", "data": {"results": {"items": list(products.items)}}}

    monkeypatch.setattr(module, "build_response", fake_build)
    monkeypatch.setattr(module, "enhance_response", lambda base, products, **kwargs: base)
    monkeypatch.setattr(module, "log_search_event", lambda **kwargs: None)
    return calls


def test_product_search_drops_shown_and_remembers_new(monkeypatch):
    _search_stubs(monkeypatch, [{"product_url": f"{PAGE_URL}a?size=36"}, {"product_url": f"{PAGE_URL}c?size=36"}])
    cache_service.set("chat:shown:u2", [f"{PAGE_URL}a"], ttl=60)
    response = ChatUseCase()._handle_product_search(None, "u2", "q", "ka", 5, 0, session=None, active_task=None,
                                                    exclude_pages=[f"{PAGE_URL}a"])
    assert [i["product_url"] for i in response["data"]["results"]["items"]] == [f"{PAGE_URL}c?size=36"]
    assert cache_service.get("chat:shown:u2") == [f"{PAGE_URL}a", f"{PAGE_URL}c"]   # показанные копятся


def test_nothing_new_honest_message(monkeypatch):
    _search_stubs(monkeypatch, [{"product_url": f"{PAGE_URL}a?size=36"}])
    response = ChatUseCase()._handle_product_search(None, "u3", "q", "ka", 5, 0, session=None, active_task=None,
                                                    exclude_pages=[f"{PAGE_URL}a"])
    assert response["data"]["results"]["items"] == []
    assert response["message"] == translate("search_no_other", "ka")



# --- 13.10: подсказка про наличие в филиале — один раз за разговор ---

def test_stock_hint_only_in_first_search_of_conversation(monkeypatch):
    calls = _search_stubs(monkeypatch, [{"product_url": f"{PAGE_URL}a?size=36"}])
    cache_service.set("chat:stock_hint:u4", None, ttl=1)
    use_case = ChatUseCase()
    use_case._handle_product_search(None, "u4", "q", "ka", 5, 0, session=None, active_task=None)
    use_case._handle_product_search(None, "u4", "q", "ka", 5, 0, session=None, active_task=None)
    assert calls == [{}, {"stock_hint": False}]         # первый ответ — с подсказкой, второй — коротко


# --- 13.10: призыв к действию по поводу + значок дефицита ---

def test_cta_on_discount_in_later_answers_rotates(monkeypatch):
    _search_stubs(monkeypatch, [{"product_url": f"{PAGE_URL}a?size=38", "price": 70.0, "regular_price": 140.0}])
    cache_service.set("chat:stock_hint:u5", True, ttl=60)        # подсказку уже говорили — это не первый ответ
    cache_service.set("chat:cta:u5", 0, ttl=60)
    use_case = ChatUseCase()
    first = use_case._handle_product_search(None, "u5", "q", "ka", 5, 0, session=None, active_task=None)
    second = use_case._handle_product_search(None, "u5", "q", "ka", 5, 0, session=None, active_task=None)
    assert first["message"].endswith(translate("cta_1", "ka"))  # скидка −50% → повод для призыва
    assert second["message"].endswith(translate("cta_2", "ka"))  # следующий раз — другая фраза


def test_scarce_sizes_label_and_cta(monkeypatch):
    _search_stubs(monkeypatch, [{"product_url": f"{PAGE_URL}g?size=38", "price": 100.0}])
    monkeypatch.setattr(module, "scarce_sizes_by_page", lambda db, pages: {f"{PAGE_URL}g": ["38", "40"]})
    cache_service.set("chat:stock_hint:u6", True, ttl=60)
    response = ChatUseCase()._handle_product_search(None, "u6", "q", "ka", 5, 0, session=None, active_task=None)
    item = response["data"]["results"]["items"][0]
    assert item["scarce_label"] == "🔥 დარჩა 2 ზომა" and item["sizes_left"] == ["38", "40"]
    assert response["message"].endswith(translate("cta_scarce", "ka"))


def test_no_cta_without_reason(monkeypatch):
    _search_stubs(monkeypatch, [{"product_url": f"{PAGE_URL}h?size=38", "price": 100.0}])
    cache_service.set("chat:stock_hint:u7", True, ttl=60)
    response = ChatUseCase()._handle_product_search(None, "u7", "q", "ka", 5, 0, session=None, active_task=None)
    assert response["message"] == "found"                       # без скидки и дефицита — без призыва


def test_prefer_discount_passed_to_search(llm_on, monkeypatch):
    fake_understanding(monkeypatch, intent="product_search", query="adidas samba", prefer_discount=True)
    captured = {}
    monkeypatch.setattr(ChatUseCase, "_handle_product_search",
                        lambda self, db, user_id, message, *args, **kwargs: captured.update(kwargs) or {"type": "product_search"})
    run("ადიდასის სამბა მოდელები თუ გაქვთ და მაჩვენე პირველ რიგში თუ არის ფასდაკლება")
    assert captured["prefer_discount"] is True and captured["discount_only"] is False





# --- 13.10: ИИ получает настоящий вопрос клиента и понятые условия ---

def test_llm_reply_gets_customer_message_and_conditions(monkeypatch):
   _search_stubs(monkeypatch, [{"product_url": f"{PAGE_URL}a?size=38"}])
   seen = {}
   monkeypatch.setattr(module, "enhance_response", lambda base, products, **kwargs: seen.update(kwargs) or base)
   ChatUseCase()._handle_product_search(None, "u6", "adidas samba", "ka", 5, 0, session=None, active_task=None,
                                        max_price=120.0, prefer_discount=True,
                                        customer_message="samba მაქვს 120 ლარამდე?")
   assert seen["customer_message"] == "samba მაქვს 120 ლარამდე?"          # не «adidas samba» после разбора
   assert seen["conditions"] == "budget up to 120 GEL; discounted products first"



# --- 15.10: ошибки моделей «понимания» видны в meta (замер скорости) ---

def test_understanding_errors_in_meta(llm_on, monkeypatch):
    def fake(message, previous_query=None, history=None):
        result = {**BASE, "intent": "small_talk", "reply": "გამარჯობა! რით დაგეხმაროთ? 🙂"}
        return {"result": result, "model": "gemini-3.1-flash-lite", "ms": 7458.3, "raw": "",
                "errors": ["gemini-3.5-flash-lite: 503 UNAVAILABLE"]}

    monkeypatch.setattr(module, "understand", fake)
    response = run("rogor xar ?")
    assert response["meta"]["understanding_errors"] == ["gemini-3.5-flash-lite: 503 UNAVAILABLE"]
    assert response["meta"]["understanding_model"] == "gemini-3.1-flash-lite"