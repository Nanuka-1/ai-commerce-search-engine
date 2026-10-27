from types import SimpleNamespace

from app.services.ai_response_service import enhance_response


def make_context(result_mode=None, matched_by=None, total_count=5):
    return SimpleNamespace(
        result_mode=result_mode,
        matched_by=matched_by,
        total_count=total_count,
    )


def test_enhance_response_keeps_response_builder_text_for_need_size():
    base_response = {
        "message": "Could you specify the size?",
        "data": {},
    }
    context = make_context(result_mode="need_size", total_count=5)

    result = enhance_response(base_response, context)

    assert result["message"] == "Could you specify the size?"
    assert result["meta"]["ai_used"] is False  # вопрос о размере — LLM не нужен
    assert result["meta"]["ai_fallback_reason"] == "not_needed"


def test_enhance_response_keeps_response_builder_text_for_size_alternatives():
    base_response = {
        "message": "Showing alternative products available in size 44.",
        "data": {},
    }
    context = make_context(matched_by="size_alternatives", total_count=3)

    result = enhance_response(base_response, context)

    assert result["message"] == "Showing alternative products available in size 44."