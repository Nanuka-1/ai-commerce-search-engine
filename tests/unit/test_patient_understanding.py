"""27.10 (решение пользователя: «понимает ИИ»): правила не поняли в сообщении ничего → ИИ ждём дольше.
Живьём 26.10: «ватлдвлвдыа» → понимание 3002 мс timeout → правила → 5 случайных топов."""
import time

import app.services.llm_understanding_service as module
from app.services import cache_service
from app.services.conversation_state_service import rules_understand_nothing

ANSWER = '{"intent": "unclear", "language": "ka", "search": {}}'


def _slow_ai(monkeypatch, seconds):
    cache_service.clear()
    monkeypatch.setattr(module, "_budget_seconds", lambda: 0.1)          # обычный лимит в тесте — 0.1 с
    monkeypatch.setattr(module.llm_client, "generate_text", lambda system, prompt: (
        time.sleep(seconds) or {"text": ANSWER, "model": "test", "ms": seconds * 1000, "errors": []}))


def test_rules_understand_nothing():
    assert rules_understand_nothing("ватлдвлвдыа") is True
    assert rules_understand_nothing("swimming") is True
    assert rules_understand_nothing("ქალის ფეხსაცმელი 36") is False      # понятно правилам
    assert rules_understand_nothing("nike") is False                     # бренд
    assert rules_understand_nothing("300 ლარამდე") is False              # бюджет
    assert rules_understand_nothing("") is False


def test_ai_gets_more_time_when_rules_understand_nothing(monkeypatch):
    _slow_ai(monkeypatch, 0.15)                      # ИИ отвечает за 0.15 с: больше 0.1, меньше 0.1 × 2.5
    understood = module.understand("ватлдвлвдыа")
    assert understood["errors"] == []
    assert understood["result"]["intent"] == "unclear"


def test_understood_message_keeps_short_budget(monkeypatch):
    _slow_ai(monkeypatch, 0.15)
    understood = module.understand("ქალის ფეხსაცმელი 36 ფასდაკლებით")
    assert understood["result"] is None and understood["errors"] == ["timeout"]