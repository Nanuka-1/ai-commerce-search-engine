from types import SimpleNamespace

import app.services.product_service as product_service


def test_execute_model_search_sets_detected_color_on_context(monkeypatch):
    product = SimpleNamespace(
        id=1,
        name="Nike Air Max Black",
        brand="Nike",
        sku="NIKE-AIRMAX-1",
        price=250.0,
        size="42",
        category_slug="men-shoes",
        style_group=None,
        color="black",
        product_url="https://topsport.ge/product/1",
        is_active=True,
    )

    monkeypatch.setattr(
        product_service,
        "get_products_by_query",
        lambda *args, **kwargs: ([product], 1),
    )
    monkeypatch.setattr(product_service.cache_service, "set", lambda *args, **kwargs: None)

    request = SimpleNamespace(
        raw_query="air max black",
        size="42",
        color="black",
        brand=None,
        limit=10,
        offset=0,
    )

    context = product_service.execute_model_search(
        db=None,
        request=request,
        normalized_query="air max black",
        model_hint="air max",
        detected_brand="nike",
        product_intent=None,
        effective_category=None,
        strategy_name="model_search",
        cache_key="test-key",
        usage_type=None,
    )

    assert context.detected_color == "black"