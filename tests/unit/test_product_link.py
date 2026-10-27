"""26.10 (этап 3, п.2): ссылка на товар topsport.ge в сообщении.
Замер: «…/adidas-bavshvis-jempri-25» читался как слова → бренд adidas + «размер 25» → чужая детская обувь."""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.use_cases.chat_use_case as chat_module
from app.db.models import Base, Product
from app.repositories.product_repository import get_products_by_page
from app.services import cache_service
from app.services.conversation_state_service import patch_from_rules
from app.services.product_link_service import find_product_link
from app.services.product_service import deal_filters
from app.services.translations import translate
from app.use_cases.chat_use_case import ChatUseCase

PAGE = "https://topsport.ge/ka/product/adidas-bavshvis-jempri-25"


@pytest.mark.parametrize("message, page, size, rest", [
    (PAGE, PAGE, None, ""),
    (f"ეს თუ გაქვთ {PAGE}", PAGE, None, "ეს თუ გაქვთ"),
    (f"{PAGE}?size=36 38 ზომაში?", PAGE, "36", "38 ზომაში?"),
    ("https://topsport.ge/en/product/adidas-bavshvis-jempri-25", PAGE, None, ""),   # в базе только /ka/
    ("https://www.topsport.ge/ka/product/adidas-bavshvis-jempri-25/", PAGE, None, ""),
])
def test_find_product_link(message, page, size, rest):
    link = find_product_link(message)
    assert (link.page, link.size, link.rest) == (page, size, rest)


@pytest.mark.parametrize("message", ["ქალის ფეხსაცმელი 36", "https://nike.com/product/x-25", "topsport.ge"])
def test_not_a_product_link(message):
    assert find_product_link(message) is None


def test_repository_finds_all_sizes_of_this_page_only():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        Product(sku="J-S", name="Adidas ბავშვის ჯემპრი", brand="Adidas", size="S", product_url=f"{PAGE}?size=S"),
        Product(sku="J-M", name="Adidas ბავშვის ჯემპრი", brand="Adidas", size="M", product_url=f"{PAGE}?size=M"),
        # соседняя страница «…-250» — начало адреса совпадает, но это другая модель
        Product(sku="X-S", name="Adidas ბავშვის ჯემპრი", brand="Adidas", size="S", product_url=f"{PAGE}0?size=S"),
    ])
    db.commit()

    items = get_products_by_page(db, PAGE)

    assert sorted(item.sku for item in items) == ["J-M", "J-S"]


def _chat(monkeypatch, cards):
    cache_service.clear()
    monkeypatch.setattr(chat_module, "get_model_cards_by_page", lambda db, page: cards)
    monkeypatch.setattr(chat_module, "get_or_create_session",
                        lambda db, user_id: SimpleNamespace(id=1, pending_clarification=None, last_query=None))
    monkeypatch.setattr(chat_module, "get_active_search_task", lambda db, session: None)
    use_case = ChatUseCase()
    use_case._handle_understanding = lambda *args, **kwargs: pytest.fail("ИИ для ссылки не нужен")
    use_case._handle_product_search = lambda *args, **kwargs: pytest.fail("ссылку не ищем как слова")
    return use_case


CARD = {"name": "Adidas ბავშვის ჯემპრი", "brand": "Adidas", "sizes": ["S", "M"], "product_url": PAGE}


def test_chat_shows_this_model_not_words_of_the_link(monkeypatch):
    use_case = _chat(monkeypatch, [CARD])
    response = use_case.process_text(db=None, user_id="u-link", message=f"ეს თუ გაქვთ {PAGE}", locale="ka")

    assert response["type"] == "product_link"
    assert response["data"]["results"]["items"] == [CARD]
    assert response["message"] == translate("product_link_found", "ka")
    assert "ჯემპრი" in response["meta"]["dialog_state"]          # дальше разговор — об этой модели
    assert "25" not in response["meta"]["dialog_state"]          # номер страницы — не размер


def test_chat_answers_about_asked_size(monkeypatch):
    use_case = _chat(monkeypatch, [CARD])
    response = use_case.process_text(db=None, user_id="u-link2", message=f"{PAGE} M ზომა თუ არის?", locale="ka")
    assert response["message"].startswith(translate("product_link_size_yes", "ka").format(size="M"))

    response = use_case.process_text(db=None, user_id="u-link3", message=f"{PAGE} XL ზომა თუ არის?", locale="ka")
    assert response["message"].startswith(translate("product_link_size_no", "ka").format(size="XL"))


def test_chat_link_not_in_catalog(monkeypatch):
    use_case = _chat(monkeypatch, [])
    response = use_case.process_text(db=None, user_id="u-link4", message=PAGE, locale="ka")
    assert response["message"] == translate("product_link_not_found", "ka")


def test_this_word_is_not_a_product():
    patch = patch_from_rules("ეს თუ გაქვთ 38")
    assert patch.product_text is None and patch.loose_text is None and patch.size == "38"


def test_other_brand_works_without_new_collection():
    # 26.10: найдено при чтении product_service — exclude_brands был ВНУТРИ if new_only
    request = SimpleNamespace(max_price=None, discount_only=False, new_only=False, exclude_brands=["Adidas"])
    assert deal_filters(request)["exclude_brands"] == ["Adidas"]