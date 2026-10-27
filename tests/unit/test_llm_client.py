from types import SimpleNamespace

import app.services.llm_client as llm

DAILY_429 = "429 RESOURCE_EXHAUSTED quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier"


def _setup(monkeypatch, behaviour: dict, enabled=True, models="model-a,gemma-b"):
    """behaviour: {model: текст ответа или Exception}"""
    monkeypatch.setattr(llm, "load_dotenv", lambda: None)
    monkeypatch.setenv("LLM_ENABLED", "true" if enabled else "false")
    monkeypatch.setenv("LLM_MODELS", models)
    calls = []

    def generate_content(model, contents, config):
        calls.append(SimpleNamespace(model=model, contents=contents, config=config))
        outcome = behaviour[model]
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(text=outcome)

    monkeypatch.setattr(llm, "_get_client", lambda: SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    return calls


def test_disabled_returns_none_without_calls(monkeypatch):
    calls = _setup(monkeypatch, {}, enabled=False)
    result = llm.generate_text("system", "prompt")
    assert result["text"] is None and result["errors"] == ["disabled"] and calls == []


def test_first_model_answers(monkeypatch):
    calls = _setup(monkeypatch, {"model-a": " გამარჯობა 👟 "})
    result = llm.generate_text("system", "prompt")
    assert result["text"] == "გამარჯობა 👟" and result["model"] == "model-a"
    assert len(calls) == 1
    assert calls[0].config.system_instruction == "system"          # Gemini: инструкция отдельно


def test_falls_back_to_gemma_on_daily_limit(monkeypatch):
    calls = _setup(monkeypatch, {"model-a": RuntimeError(DAILY_429), "gemma-b": "ტექსტი"})
    result = llm.generate_text("system", "prompt")
    assert result["text"] == "ტექსტი" and result["model"] == "gemma-b"
    assert "model-a" in result["errors"][0]
    assert calls[1].contents == "system\n\nprompt"                 # Gemma: инструкция внутри текста
    assert calls[1].config.system_instruction is None


def test_all_models_fail_returns_none(monkeypatch):
    _setup(monkeypatch, {"model-a": TimeoutError("timeout"), "gemma-b": ""})
    result = llm.generate_text("system", "prompt")
    assert result["text"] is None and len(result["errors"]) == 2   # шаблон


def test_empty_model_list_is_reported(monkeypatch):
    _setup(monkeypatch, {}, models="")
    assert "LLM_MODELS is empty" in llm.generate_text("s", "p")["errors"]


def test_timeout_never_below_api_minimum(monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "5")
    assert llm._timeout_seconds() == 10          # API: "Minimum allowed deadline is 10s"
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "15")
    assert llm._timeout_seconds() == 15