from types import SimpleNamespace

from app.services import search_event_service


def test_log_search_event_increments_fallback_level_metric(monkeypatch):
    calls = {}

    class FakeLabels:
        def inc(self):
            calls["inc_called"] = True

    class FakeFallbackMetric:
        def labels(self, fallback_level):
            calls["fallback_level"] = fallback_level
            return FakeLabels()

    def fake_create_search_event(**kwargs):
        return kwargs

    monkeypatch.setattr(
        search_event_service,
        "search_fallback_level_total",
        FakeFallbackMetric(),
    )

    monkeypatch.setattr(
        search_event_service,
        "create_search_event",
        fake_create_search_event,
    )

    search_context = SimpleNamespace(
        search_strategy="model_search",
        matched_by="same_size",
        fallback_level="same_size",
    )

    search_event_service.log_search_event(
        db=None,
        user_id="test_user",
        query="nike air max 42",
        locale="en",
        intent="product_search",
        items=[],
        search_context=search_context,
        ai_meta={},
    )

    assert calls["fallback_level"] == "same_size"
    assert calls["inc_called"] is True

def test_log_search_event_skips_fallback_metric_when_none(monkeypatch):
    calls = {}

    class FakeLabels:
        def inc(self):
            calls["inc_called"] = True

    class FakeFallbackMetric:
        def labels(self, fallback_level):
            calls["fallback_level"] = fallback_level
            return FakeLabels()

    def fake_create_search_event(**kwargs):
        return kwargs

    monkeypatch.setattr(
        search_event_service,
        "search_fallback_level_total",
        FakeFallbackMetric(),
    )

    monkeypatch.setattr(
        search_event_service,
        "create_search_event",
        fake_create_search_event,
    )

    search_context = SimpleNamespace(
        search_strategy="model_search",
        matched_by="exact_model",
        fallback_level=None,
    )

    search_event_service.log_search_event(
        db=None,
        user_id="test_user",
        query="nike air max",
        locale="en",
        intent="product_search",
        items=[],
        search_context=search_context,
        ai_meta={},
    )

    assert "fallback_level" not in calls
    assert "inc_called" not in calls