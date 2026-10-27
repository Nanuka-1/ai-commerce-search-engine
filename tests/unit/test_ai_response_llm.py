import time
from types import SimpleNamespace

import app.services.ai_response_service as ai

PEGASUS = {"name": "Nike Air Zoom Pegasus 41", "brand": "Nike", "sizes": ["42"], "price": 318.0}
TEMPLATE = "თქვენი ზომა 42 ვიპოვე! კონკრეტულ ფილიალში მარაგი გადაამოწმეთ პროდუქტის გვერდზე."


def _context(**overrides):
    values = dict(query="pegasus 42", items=[PEGASUS], total_count=1, result_mode="normal")
    values.update(overrides)
    return SimpleNamespace(**values)


def _base():
    return {"type": "product_search", "message": TEMPLATE, "data": {}}


def _llm(monkeypatch, text=None, errors=(), delay=0.0, enabled=True):
    monkeypatch.setattr(ai.llm_client, "is_enabled", lambda: enabled)

    def generate_text(system, prompt):
        time.sleep(delay)
        return {"text": text, "model": "gemini-3.5-flash-lite" if text else None, "errors": list(errors), "ms": 1.0}

    monkeypatch.setattr(ai.llm_client, "generate_text", generate_text)


def test_valid_llm_text_replaces_template_and_keeps_it(monkeypatch):
    _llm(monkeypatch, text="კარგი ამბავია 👟 თქვენი ზომა 42 ვიპოვეთ — მარაგი ფილიალში გადაამოწმეთ საიტზე.")
    response = ai.enhance_response(_base(), _context())
    assert response["message"].startswith("კარგი ამბავია")
    assert response["template_message"] == TEMPLATE
    assert response["meta"]["ai_used"] is True and response["meta"]["ai_model"] == "gemini-3.5-flash-lite"


def test_invented_price_is_rejected_template_kept(monkeypatch):
    _llm(monkeypatch, text="Pegasus მხოლოდ 199 ლარად! 🔥")
    response = ai.enhance_response(_base(), _context())
    assert response["message"] == TEMPLATE
    assert response["meta"]["ai_fallback_reason"] == "rejected: unknown_numbers:199"


def test_not_needed_for_size_question_and_empty_results(monkeypatch):
    _llm(monkeypatch, text="არ უნდა გამოიძახოს")
    for context in (_context(result_mode="need_size"), _context(items=[], total_count=0)):
        response = ai.enhance_response(_base(), context)
        assert response["message"] == TEMPLATE and response["meta"]["ai_fallback_reason"] == "not_needed"


def test_disabled_and_unavailable_fall_back(monkeypatch):
    _llm(monkeypatch, enabled=False)
    assert ai.enhance_response(_base(), _context())["meta"]["ai_fallback_reason"] == "disabled"
    _llm(monkeypatch, text=None, errors=["gemini: 429"])
    response = ai.enhance_response(_base(), _context())
    assert response["message"] == TEMPLATE
    assert response["meta"]["ai_fallback_reason"].startswith("llm_unavailable: gemini: 429")


def test_slow_llm_hits_budget_and_template_is_returned(monkeypatch):
    monkeypatch.setenv("LLM_BUDGET_SECONDS", "0.2")
    _llm(monkeypatch, text="ძალიან გვიან", delay=1.0)
    started = time.perf_counter()
    response = ai.enhance_response(_base(), _context())
    assert time.perf_counter() - started < 0.8                     # клиент не ждал модель
    assert response["message"] == TEMPLATE and response["meta"]["ai_fallback_reason"] == "timeout"


def test_english_template_gets_english_check(monkeypatch):
    _llm(monkeypatch, text="ზომა 42 ვიპოვეთ")                      # грузинский ответ на английский шаблон
    base = {"message": "We found your size 42! Please check stock in a store.", "data": {}}
    response = ai.enhance_response(base, _context())
    assert response["meta"]["ai_fallback_reason"] == "rejected: wrong_language"