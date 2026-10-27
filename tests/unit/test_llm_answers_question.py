"""13.10: ИИ видит НАСТОЯЩИЙ вопрос клиента и понятые условия → отвечает на него («კი, ვიპოვე…»)."""
from types import SimpleNamespace

import app.services.ai_response_service as ai
from app.services.llm_text_service import build_facts, build_prompt, describe_conditions

SAMBA = {"name": "Adidas Samba OG", "brand": "Adidas", "sizes": ["38"], "price": 299.0}
TEMPLATE = "ზომა 38 ✅ აი 5 ვარიანტი 👇"


def _context():
    return SimpleNamespace(query="adidas samba 38", items=[SAMBA], total_count=1, result_mode="normal")


def test_describe_conditions():
    assert describe_conditions(size="38", max_price=120.0, prefer_discount=True) == \
        "size 38; budget up to 120 GEL; discounted products first"
    assert describe_conditions(discount_only=True, prefer_discount=True) == "only discounted products"
    assert describe_conditions() is None


def test_facts_contain_customer_question_and_conditions():
    facts = build_facts(_context(), TEMPLATE, "გაქვთ samba 38 ზომაში?", "size 38")
    assert facts.splitlines()[:2] == ["CUSTOMER MESSAGE: გაქვთ samba 38 ზომაში?", "CUSTOMER CONDITIONS: size 38"]
    assert "CUSTOMER CONDITIONS" not in build_facts(_context(), TEMPLATE, "samba 38")   # без условий — как раньше


def test_prompt_asks_to_answer_first_and_be_honest():
    system, _ = build_prompt(_context(), TEMPLATE, "x", "ka")
    assert "First answer the CUSTOMER MESSAGE directly" in system
    assert "never say \"yes\" then" in system


def _capture(monkeypatch, text):
    seen = {}
    monkeypatch.setattr(ai.llm_client, "is_enabled", lambda: True)

    def generate_text(system, prompt):
        seen["prompt"] = prompt
        return {"text": text, "model": "test", "errors": [], "ms": 1.0}

    monkeypatch.setattr(ai.llm_client, "generate_text", generate_text)
    return seen


def test_enhance_response_sends_real_customer_message(monkeypatch):
    seen = _capture(monkeypatch, "კი, Samba 38 ზომაში ვიპოვე 👟 აი ვარიანტები.")
    base = {"type": "product_search", "message": TEMPLATE, "data": {}}
    response = ai.enhance_response(base, _context(), customer_message="გაქვთ samba 38 ზომაში?",
                                   conditions="size 38")
    assert "CUSTOMER MESSAGE: გაქვთ samba 38 ზომაში?" in seen["prompt"]
    assert "CUSTOMER CONDITIONS: size 38" in seen["prompt"]
    assert response["message"].startswith("კი, Samba 38")
    assert response["meta"]["ai_used"] is True


def test_without_customer_message_uses_search_query_as_before(monkeypatch):
    seen = _capture(monkeypatch, "კი, ვიპოვე 👟")
    ai.enhance_response({"message": TEMPLATE, "data": {}}, _context())
    assert "CUSTOMER MESSAGE: adidas samba 38" in seen["prompt"]