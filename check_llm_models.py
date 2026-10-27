
"""
Шаг 3.7b: какие текстовые модели доступны ключу и как быстро отвечают. В базу не пишет.

1) Список моделей, которые умеют generateContent, — только Flash Lite и Gemma (наши кандидаты).
2) По одному короткому запросу к каждой модели из LLM_MODELS (.env) — время ответа и текст.
   Тратит по 1 обращению на модель (из 500 / 14 400 в день).

Запуск: Run в PyCharm (корень проекта).
"""
import time

from app.services.embedding_client import _get_client
from app.services.llm_client import _call_model, configured_models

CANDIDATE_WORDS = ("flash-lite", "gemma")


def list_candidates():
    print("Доступные модели-кандидаты (generateContent):")
    for model in _get_client().models.list():
        name = model.name.replace("models/", "")
        actions = getattr(model, "supported_actions", None) or []
        if any(word in name.lower() for word in CANDIDATE_WORDS) and "generateContent" in actions:
            print(f"  {name}")


def try_models():
    models = configured_models()
    if not models:
        print("\nLLM_MODELS в .env пуст — впишите имена из списка выше через запятую.")
        return
    system = "You are a polite sales consultant. Answer in Georgian, one short sentence, formally (თქვენ)."
    prompt = "Greet the customer who is looking for running shoes in size 42."
    for model in models:
        started = time.perf_counter()
        try:
            text = _call_model(model, system, prompt)
            print(f"\n{model}: {time.perf_counter() - started:.1f} с\n  {text}")
        except Exception as error:
            print(f"\n{model}: ОШИБКА за {time.perf_counter() - started:.1f} с — {str(error)[:200]}")


if __name__ == "__main__":
    list_candidates()
    try_models()