"""
Клиент LLM для текста ответа (шаг 3.7b). Только вызов модели — ЧТО спрашивать и как проверять
ответ, решает llm_text_service.

Цепочка моделей (бесплатный уровень, лимиты AI Studio 09.10):
  1. Gemini 3.5 Flash Lite — 15 в минуту, 500 в день;
  2. Gemma 4 31B          — 30 в минуту, 14 400 в день (TPM 16K).
Модель недоступна / лимит / ошибка / таймаут → следующая. Все не ответили → None (клиент получит шаблон).

Настройки — в .env:
  LLM_ENABLED=true                         (по умолчанию выключено — тесты и чат без LLM)
  LLM_MODELS=<id1>,<id2>                   (точные имена берём из check_llm_models.py, не угадываем)
  LLM_TIMEOUT_SECONDS=10                   (Gemini API не принимает дедлайн меньше 10 с — проверено 09.10)
"""
import logging
import os
import time

from dotenv import load_dotenv

from app.services.embedding_client import _get_client   # тот же ключ GEMINI_API_KEY

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10
MIN_API_DEADLINE_SECONDS = 10   # 400 INVALID_ARGUMENT "Minimum allowed deadline is 10s" (09.10)
MAX_OUTPUT_TOKENS = 1024     # с запасом: у части моделей "размышления" тоже считаются в выходные токены
TEMPERATURE = 0.4            # немного живости, без фантазий


def is_enabled() -> bool:
    load_dotenv()
    return os.getenv("LLM_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def configured_models() -> list[str]:
    load_dotenv()
    return [name.strip() for name in os.getenv("LLM_MODELS", "").split(",") if name.strip()]


def _timeout_seconds() -> float:
    try:
        value = float(os.getenv("LLM_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    except ValueError:
        value = DEFAULT_TIMEOUT_SECONDS
    return max(value, MIN_API_DEADLINE_SECONDS)


def _is_gemma(model: str) -> bool:
    return "gemma" in model.lower()


def _call_model(model: str, system: str, prompt: str) -> str:
    from google.genai import types

    if _is_gemma(model):
        # Gemma в Gemini API может не принимать system_instruction — кладём инструкцию в текст запроса
        contents, system_instruction = f"{system}\n\n{prompt}", None
    else:
        contents, system_instruction = prompt, system

    result = _get_client().models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=TEMPERATURE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            http_options=types.HttpOptions(timeout=int(_timeout_seconds() * 1000)),   # миллисекунды
            # инструменты не используем — выключаем "автоматический вызов функций" (и его предупреждение)
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    return (result.text or "").strip()


def generate_text(system: str, prompt: str) -> dict:
    """{"text": str | None, "model": str | None, "errors": [...], "ms": float}
    Никогда не бросает исключение: при любой проблеме text=None → вызывающий код берёт шаблон."""
    started = time.perf_counter()
    errors = []
    if not is_enabled():
        return {"text": None, "model": None, "errors": ["disabled"], "ms": 0.0}

    for model in configured_models():
        try:
            text = _call_model(model, system, prompt)
            if text:
                return {"text": text, "model": model, "errors": errors,
                        "ms": round((time.perf_counter() - started) * 1000, 1)}
            errors.append(f"{model}: empty")
        except Exception as error:   # лимит, таймаут, сеть, неверное имя модели — пробуем следующую
            errors.append(f"{model}: {str(error)[:120]}")
            logger.warning("LLM %s unavailable: %s", model, error)

    if not configured_models():
        errors.append("LLM_MODELS is empty")
    return {"text": None, "model": None, "errors": errors,
            "ms": round((time.perf_counter() - started) * 1000, 1)}