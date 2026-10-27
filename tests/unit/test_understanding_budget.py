"""15.10: «понимание» ИИ не дольше лимита — иначе чат идёт по правилам (бюджет/скидка — deal_rules_service)."""
import time

import app.services.llm_understanding_service as service
from app.services import cache_service


def test_slow_understanding_is_not_awaited(monkeypatch):
    cache_service.clear()
    monkeypatch.setenv("LLM_UNDERSTANDING_BUDGET_SECONDS", "0.2")

    def slow(system, prompt):
        time.sleep(1.0)
        return {"text": '{"intent": "unclear"}', "model": "m", "errors": [], "ms": 1000.0}

    monkeypatch.setattr(service.llm_client, "generate_text", slow)
    started = time.perf_counter()
    response = service.understand("კაცის სარბენი 42, 200 ლარამდე?")
    assert time.perf_counter() - started < 0.8              # клиент не ждал модель
    assert response["result"] is None and response["errors"] == ["timeout"]


def test_fast_understanding_is_used(monkeypatch):
    cache_service.clear()
    text = '{"intent": "product_search", "search": {"query": "მამაკაცის სარბენი ფეხსაცმელი 42", "max_price": 200}}'
    monkeypatch.setattr(service.llm_client, "generate_text",
                        lambda system, prompt: {"text": text, "model": "m", "errors": [], "ms": 900.0})
    response = service.understand("კაცის სარბენი 42, 200 ლარამდე?")
    assert response["result"]["max_price"] == 200.0
    assert response["model"] == "m" and response["ms"] == 900.0