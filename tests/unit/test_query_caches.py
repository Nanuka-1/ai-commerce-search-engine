"""15.10: кэш того, что НЕ зависит от каталога — точка запроса (эмбеддинг) и понимание первого сообщения."""
from app.services import cache_service, embedding_client
import app.services.llm_understanding_service as understanding

UNDERSTOOD = '{"intent": "product_search", "search": {"query": "მამაკაცის სარბენი ფეხსაცმელი 42"}}'


def test_query_embedding_is_cached(monkeypatch):
    cache_service.clear()
    calls = []
    monkeypatch.setattr(embedding_client, "_embed",
                        lambda texts, task_type, max_retries=5: calls.append(texts) or [[0.6, 0.8]])
    assert embedding_client.embed_query("Nike  42") == [0.6, 0.8]
    assert embedding_client.embed_query("nike 42") == [0.6, 0.8]      # тот же запрос → без Gemini
    assert len(calls) == 1


def _fake_llm(monkeypatch):
    calls = []

    def fake(system, prompt):
        calls.append(prompt)
        return {"text": UNDERSTOOD, "model": "gemini-3.5-flash-lite", "errors": [], "ms": 900.0}

    monkeypatch.setattr(understanding.llm_client, "generate_text", fake)
    return calls


def test_first_message_understanding_is_cached(monkeypatch):
    cache_service.clear()
    calls = _fake_llm(monkeypatch)
    first = understanding.understand("კაცის სარბენი 42")
    second = understanding.understand("კაცის  სარბენი 42")
    assert len(calls) == 1
    assert second["result"] == first["result"]
    assert second["model"] == "cache" and second["ms"] == 0.0


def test_conversation_is_not_cached(monkeypatch):
    # в разговоре «и 43?» зависит от прошлых сообщений — кэш дал бы чужой смысл
    cache_service.clear()
    calls = _fake_llm(monkeypatch)
    understanding.understand("და 43?", history=["კაცის სარბენი 42"])
    understanding.understand("და 43?", history=["ქალის ქურთუკი M"])
    understanding.understand("და 43?", previous_query="კაცის სარბენი 42")
    assert len(calls) == 3


def test_failed_understanding_is_not_cached(monkeypatch):
    cache_service.clear()
    monkeypatch.setattr(understanding.llm_client, "generate_text",
                        lambda system, prompt: {"text": None, "model": None, "errors": ["503"], "ms": 1.0})
    understanding.understand("კაცის სარბენი 42")
    assert cache_service.get(understanding.understanding_cache_key("კაცის სარბენი 42")) is None