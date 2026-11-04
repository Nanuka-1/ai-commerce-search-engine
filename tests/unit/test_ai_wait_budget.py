"""04.11 (замер на Vercel: наш код 0.1 с, ожидание Gemini 3 + 5 с): текст ИИ ждём не дольше 3 с,
а если в этом сообщении ИИ-понимание уже не успело — текст ИИ не зовём вовсе (сразу шаблон)."""
from types import SimpleNamespace

from app.services import ai_response_service as service
from app.services import request_timings

BASE = {"message": "ზომა 36 ✅ აი 5 ვარიანტი 👇", "data": {}}


def _llm_ready(monkeypatch):
    calls = []
    monkeypatch.setattr(service, "should_use_llm", lambda context: True)
    monkeypatch.setattr(service.llm_client, "is_enabled", lambda: True)
    monkeypatch.setattr(service, "build_prompt", lambda *args: ("system", "facts"))
    monkeypatch.setattr(service.llm_client, "generate_text",
                        lambda system, facts: calls.append(1) or {"text": None, "errors": ["test"]})
    return calls


def _in_request(note=None):
    timings, token, started = request_timings.start()
    if note is not None:
        request_timings.note_skipped(note)
    return timings, token, started


def test_text_budget_is_three_seconds(monkeypatch):
    monkeypatch.delenv("LLM_BUDGET_SECONDS", raising=False)
    assert service.DEFAULT_BUDGET_SECONDS == 3
    assert service._budget_seconds() == 3


def test_understanding_timed_out_flag():
    assert request_timings.understanding_timed_out() is False            # вне запроса чата
    for note, expected in ((["timeout"], True), (["429 RESOURCE_EXHAUSTED"], False), (None, False)):
        timings, token, started = _in_request(note)
        try:
            assert request_timings.understanding_timed_out() is expected
        finally:
            request_timings.finish({}, timings, token, started)


def test_no_text_call_after_understanding_timeout(monkeypatch):
    calls = _llm_ready(monkeypatch)
    timings, token, started = _in_request(["timeout"])
    try:
        response = service.enhance_response(BASE, SimpleNamespace(query="ქალის ფეხსაცმელი 36"))
    finally:
        request_timings.finish({}, timings, token, started)
    assert calls == []                                                   # Gemini второй раз не звали
    assert response["message"] == BASE["message"]                        # шаблон
    assert response["meta"]["ai_fallback_reason"] == "skipped_after_timeout"


def test_text_still_called_when_understanding_was_fine(monkeypatch):
    calls = _llm_ready(monkeypatch)
    timings, token, started = _in_request()
    try:
        service.enhance_response(BASE, SimpleNamespace(query="ქალის ფეხსაცმელი 36"))
    finally:
        request_timings.finish({}, timings, token, started)
    assert calls == [1]