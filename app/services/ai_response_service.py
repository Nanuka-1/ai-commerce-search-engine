"""
AI-слой ответа (шаг 3.7c): живое вступление от LLM вместо шаблона — только если оно прошло проверку.

  поиск → бизнес-правила → шаблонный текст (response_builder)
                                   │
            should_use_llm? ── нет ─┴─→ шаблон
                 │ да
         build_prompt → generate_text (цепочка моделей, общий предел времени)
                 │
         validate_llm_text ── не прошёл ─→ шаблон
                 │ прошёл
            текст LLM (шаблон сохраняется в response["template_message"])

Чат никогда не ломается из-за LLM: любая проблема → шаблон + причина в meta.
"""
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from app.schemas.search_context import SearchContext
from app.services import llm_client
from app.services.llm_text_service import build_prompt, clean_llm_text, should_use_llm, validate_llm_text

DEFAULT_BUDGET_SECONDS = 5     # клиент ждёт LLM не дольше; замер 09.10: 0.9–3.1 с
GEORGIAN = re.compile("[Ⴀ-ჿ]")

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm")


def _budget_seconds() -> float:
    try:
        return float(os.getenv("LLM_BUDGET_SECONDS", DEFAULT_BUDGET_SECONDS))
    except ValueError:
        return DEFAULT_BUDGET_SECONDS


def _language_of(text: str) -> str:
    # Шаблон уже написан на языке клиента (response_builder) — берём язык из него.
    return "ka" if GEORGIAN.search(text or "") else "en"


def _with_meta(base_response: dict, **meta) -> dict:
    response = base_response.copy()
    response["meta"] = {**response.get("meta", {}), **meta}
    return response


def _template(base_response: dict, reason: str, model=None, ms=None, rejected_text=None) -> dict:
    return _with_meta(base_response, ai_used=False, ai_mode="template", ai_model=model,
                      ai_fallback_reason=reason, ai_response_time_ms=ms,
                      ai_rejected_text=rejected_text)      # для отладки (3.7d), клиенту не показывается


def enhance_response(base_response: dict, context: SearchContext,
                     customer_message: str | None = None, conditions: str | None = None) -> dict:
    """customer_message — то, что НАПИСАЛ клиент (13.10); без него — запрос поиска, как раньше."""
    original_message = base_response.get("message")
    if not original_message:
        return base_response
    if context is None:
        return _template(base_response, "context_missing")
    if not should_use_llm(context):
        return _template(base_response, "not_needed")      # не нашли / вопрос о размере — шаблон точнее
    if not llm_client.is_enabled():
        return _template(base_response, "disabled")

    language = _language_of(original_message)
    system, facts = build_prompt(context, original_message, customer_message or context.query or "", language,
                                 conditions)

    started = time.perf_counter()
    future = _executor.submit(llm_client.generate_text, system, facts)
    try:
        result = future.result(timeout=_budget_seconds())
    except FutureTimeout:
        ms = round((time.perf_counter() - started) * 1000, 1)
        return _template(base_response, "timeout", ms=ms)   # ответ модели (если придёт) просто не используем
    except Exception as error:                               # страховка: generate_text и так не бросает
        return _template(base_response, f"error: {str(error)[:80]}")

    ms = round((time.perf_counter() - started) * 1000, 1)
    if not result.get("text"):
        return _template(base_response, "llm_unavailable: " + "; ".join(result.get("errors", []))[:200], ms=ms)

    text = clean_llm_text(result["text"])                 # убрать "Hello!/მოგესალმებით!" в начале
    ok, reason = validate_llm_text(text, facts, language)
    if not ok:
        return _template(base_response, f"rejected: {reason}", model=result.get("model"), ms=ms,
                         rejected_text=text)

    response = _with_meta(base_response, ai_used=True, ai_mode="llm", ai_model=result.get("model"),
                          ai_fallback_reason=None, ai_response_time_ms=ms)
    response["template_message"] = original_message      # для сравнения и отладки (3.7d)
    response["message"] = text
    return response