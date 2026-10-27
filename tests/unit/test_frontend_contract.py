from types import SimpleNamespace

from app.schemas.chat import ChatMessageResponse
from app.services.product_serializer import serialize_product


def test_card_has_photo_and_regular_price():
    product = SimpleNamespace(id=1, sku="A-42", name="Nike Pegasus 41", brand="Nike", price=318.0, size="42",
                              product_url="https://topsport.ge/ka/product/p", is_active=True,
                              category_slug="მამაკაცი", color=None,
                              image_url="https://topsport.ge/img/p.jpg", regular_price=455.0)
    card = serialize_product(product)
    assert card["image_url"] == "https://topsport.ge/img/p.jpg"
    assert card["regular_price"] == 455.0


def test_chat_response_keeps_meta_for_demo_page():
    response = ChatMessageResponse(type="product_search", message="ok",
                                   meta={"ai_used": True, "ai_model": "gemini-3.5-flash-lite"})
    assert response.model_dump()["meta"]["ai_used"] is True