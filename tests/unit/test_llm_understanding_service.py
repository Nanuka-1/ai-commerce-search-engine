from app.services.llm_understanding_service import parse_understanding, reply_is_safe, understand


def test_parse_valid_json_in_code_fence():
    text = """```json
{"intent": "product_search", "language": "ka",
 "search": {"query": "ბავშვის ფეხსაცმელი 33", "gender": "kids", "size": 33, "brand": null,
            "max_price": "100", "discount_only": false, "gift": false},
 "store_topic": null, "refers_to_previous": false, "reply": null}
```"""
    result = parse_understanding(text)
    assert result["intent"] == "product_search"
    assert result["query"] == "ბავშვის ფეხსაცმელი 33"
    assert result["gender"] == "kids"
    assert result["size"] == "33"
    assert result["max_price"] == 100.0


def test_parse_rejects_broken_or_unknown():
    assert parse_understanding(None) is None
    assert parse_understanding("not json") is None
    assert parse_understanding('{"intent": "buy_everything"}') is None
    assert parse_understanding('["product_search"]') is None


def test_unsafe_values_become_safe():
    result = parse_understanding('{"intent": "product_search", "search": {"query": "  ", "gender": "aliens"}}')
    assert result["intent"] == "unclear"          # искать нечего
    assert result["gender"] is None

    result = parse_understanding('{"intent": "store_question", "store_topic": "weather"}')
    assert result["intent"] == "unclear"


def test_small_talk_reply_barriers():
    ok = parse_understanding('{"intent": "small_talk", "reply": "მადლობა, კარგად! რით შემიძლია დაგეხმაროთ? 🙂"}')
    assert ok["reply"].startswith("მადლობა")

    for bad in ("ეს მოდელი გვაქვს მარაგში", "see https://topsport.ge", "ფასი 100 ლარია"):
        result = parse_understanding('{"intent": "small_talk", "reply": "%s"}' % bad)
        assert result["intent"] == "small_talk" and result["reply"] is None   # → наш шаблон
        assert result["reply_rejected"] == bad                                  # видно при отладке

    assert reply_is_safe(None) is False
    # замер 12.10: приветствие + ответ + вопрос — 3 коротких предложения, это нормально
    assert reply_is_safe("გამარჯობა! გმადლობთ, კარგად ვარ. რით შემიძლია დაგეხმაროთ? 😊") is True
    assert reply_is_safe("ერთი. ორი. სამი. ოთხი.") is False


def test_reply_only_for_small_talk():
    result = parse_understanding('{"intent": "product_question", "reply": "კარგი არჩევანია"}')
    assert result["reply"] is None


def test_understand_without_llm_never_breaks():
    # tests/conftest.py: LLM_ENABLED=false
    response = understand("rogor xar ?")
    assert response["result"] is None
    assert "disabled" in response["errors"]


def test_needs_understanding_only_when_rules_did_not_understand():
    from app.services.llm_understanding_service import needs_understanding
    assert needs_understanding("rogor xar ?", brand=None, category=None, is_refinement=False) is True
    assert needs_understanding("nike 42", brand="nike", category=None, is_refinement=False) is False
    assert needs_understanding("ქალის ქურთუკი", brand=None, category="ქალ", is_refinement=False) is False
    assert needs_understanding("43", brand=None, category=None, is_refinement=True) is False
    assert needs_understanding("https://topsport.ge/ka/product/ua-phantom-4?size=42",
                               brand=None, category=None, is_refinement=False) is False
    assert needs_understanding("  ", brand=None, category=None, is_refinement=False) is False


def test_needs_understanding_for_budget_and_discount():
    # U2.3: бюджет / скидку правила не понимают → ИИ, даже если бренд или пол уже найдены
    from app.services.llm_understanding_service import needs_understanding
    assert needs_understanding("ბავშვის ფეხსაცმელი ფასდაკლებით", brand=None, category="ბავშვ",
                               is_refinement=False) is True
    assert needs_understanding("nike air max 42 cheaper than 300", brand="nike", category=None,
                               is_refinement=False) is True
    assert needs_understanding("სარბენი ფეხსაცმელი 100 ლარამდე", brand=None, category=None,
                               is_refinement=False) is True
    assert needs_understanding("nike 42", brand="nike", category=None, is_refinement=False) is False



def test_prompt_contains_recent_messages():
    from app.services.llm_understanding_service import build_understanding_prompt
    _, prompt = build_understanding_prompt("მე ბიჭის მინდა", "ფეხსაცმელი 36", ["a", "b", "c", "d", "e"])
    assert "RECENT CUSTOMER MESSAGES (oldest first): b | c | d | e" in prompt     # только последние 4
    assert "PREVIOUS SEARCH: ფეხსაცმელი 36" in prompt
    assert prompt.endswith("CUSTOMER MESSAGE: მე ბიჭის მინდა")



def test_parse_wants_other():
    result = parse_understanding('{"intent": "product_search", "search": {"query": "ფეხსაცმელი"}, "wants_other": true}')
    assert result["wants_other"] is True
    assert parse_understanding('{"intent": "unclear"}')["wants_other"] is False


def test_parse_prefer_discount():
    # 13.10: «პირველ რიგში თუ არის ფასდაკლება» — скидки первыми, но не только они
    result = parse_understanding('{"intent": "product_search", "search": {"query": "adidas samba", "prefer_discount": true}}')
    assert result["prefer_discount"] is True and result["discount_only"] is False
    both = parse_understanding('{"intent": "product_search", "search": {"query": "x", "prefer_discount": true, "discount_only": true}}')
    assert both["discount_only"] is True and both["prefer_discount"] is False       # «только скидки» сильнее