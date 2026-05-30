import time
from app.schemas.search_context import SearchContext


def enhance_response(base_response: dict, context: SearchContext) -> dict:
    """
    Demo AI layer with fallback and basic observability.
    """

    original_message = base_response.get("message")

    if not original_message:
        return base_response

    if context is None:
        response = base_response.copy()

        response["meta"] = {
            **response.get("meta", {}),
            "ai_used": False,
            "ai_mode": "demo",
            "ai_fallback_used": True,
            "ai_error": "context_missing",
        }

        return response

    if context.total_count == 0:
        response = base_response.copy()

        response["meta"] = {
            **response.get("meta", {}),
            "ai_used": False,
            "ai_mode": "demo",
            "ai_fallback_used": False,
            "ai_error": None,
        }

        return response

    start_time = time.perf_counter()

    try:
        ai_message = _build_demo_ai_message(
            original_message=original_message,
            result_mode=context.result_mode,
            context=context,
        )

        ai_response_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        response = base_response.copy()
        response["message"] = ai_message
        response["meta"] = {
            **response.get("meta", {}),
            "ai_used": True,
            "ai_mode": "demo",
            "ai_fallback_used": False,
            "ai_response_time_ms": ai_response_time_ms,
        }
        return response

    except Exception as error:
        ai_response_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        response = base_response.copy()
        response["meta"] = {
            **response.get("meta", {}),
            "ai_used": False,
            "ai_mode": "demo",
            "ai_fallback_used": True,
            "ai_response_time_ms": ai_response_time_ms,
            "ai_error": str(error),
        }
        return response


def _build_demo_ai_message(
    original_message: str,
    result_mode: str | None,
    context: SearchContext,
) -> str:
    if context.matched_by == "size_alternatives":
        return original_message

    if result_mode == "need_size":
        return (
            f"I found options for {context.model_hint}. "
            "Please specify the size so I can check the most relevant items."
        )

    if result_mode == "need_model":
        if context.total_count == 1:
            return (
                "I found one product that matches the brand and size. "
                "If you need a specific model, you can send the model name, SKU, product link, or a photo."
            )

        return (
            f"I found {context.total_count} products that match the size. "
            "Please specify the exact model to narrow it down. "
            "You can send the model name, SKU, product link, or a photo."
        )

    if result_mode == "fallback_similar":
        return (
            f"I could not find the exact model {context.model_hint}, "
            "but I found similar options you may want to check."
        )

    return original_message