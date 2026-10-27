"""21.10: «სხვა ბრენდის მოდელები მაჩვენეთ» → тот же поиск без уже показанных брендов.
Живьём: дважды Adidas, хотя под условия (детская новинка 36, ≤ 300 ₾) есть 23 модели Nike."""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.use_cases.chat_use_case as chat_module
from app.db.models import Base, Product
from app.repositories.product_repository import deal_conditions, get_products_by_query
from app.services import cache_service
from app.services.conversation_state_service import SearchState, state_to_dict
from app.use_cases.chat_use_case import ChatUseCase, is_other_brand_request, wants_other_brand


@pytest.mark.parametrize("message, expected", [
    ("სხვა ბრენდის მოდელები მაჩვენეთ", True),
    ("other brands please", True),
    ("different brand", True),
    ("სხვა მოდელები", False),               # другие модели — это «ещё», не другой бренд
    ("nike 42", False),
])
def test_wants_other_brand(message, expected):
    assert wants_other_brand(message) is expected


@pytest.mark.parametrize("message, expected", [
    ("სხვა ბრენდის მოდელები მაჩვენეთ", True),
    ("სხვა ბრენდის სარბენი ფეხსაცმელი", False),   # свой товар → обычный путь (ИИ / правила)
])
def test_is_other_brand_request(message, expected):
    assert is_other_brand_request(message) is expected


def test_exclude_brands_is_a_database_filter():
    sql = " ".join(str(condition.compile(compile_kwargs={"literal_binds": True}))
                   for condition in deal_conditions(exclude_brands=["Adidas"]))
    assert "brand NOT IN" in sql and "Adidas" in sql


def test_repository_skips_excluded_brands():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        Product(sku="A-36", name="ბავშვის ფეხსაცმელი A", brand="Adidas", size="36", product_url="u/a?size=36"),
        Product(sku="N-36", name="ბავშვის ფეხსაცმელი N", brand="Nike", size="36", product_url="u/n?size=36"),
    ])
    db.commit()

    items, total = get_products_by_query(db, "ბავშვის ფეხსაცმელი", size="36", exclude_brands=["Adidas"])

    assert [item.brand for item in items] == ["Nike"]
    assert total == 1


def test_chat_other_brand_keeps_conditions_and_excludes_shown_brands(monkeypatch):
    cache_service.clear()
    # 26.10: условия разговора — в карточке (раньше chat:deal)
    cache_service.set("chat:state:u-ob", state_to_dict(SearchState(
        product="ფეხსაცმელი", product_text="ფეხსაცმელი", size="36", max_price=300, new_only=True)))
    cache_service.set("chat:brands:u-ob", ["Adidas"])
    session = SimpleNamespace(id=1, pending_clarification=None, last_query=None, status="active")
    monkeypatch.setattr(chat_module, "get_or_create_session", lambda db, user_id: session)
    monkeypatch.setattr(chat_module, "get_active_search_task",
                        lambda db, session: SimpleNamespace(query="ფეხსაცმელი 36"))
    use_case = ChatUseCase()
    use_case._handle_understanding = lambda *args, **kwargs: pytest.fail("ИИ не нужен")
    searched = []
    use_case._handle_product_search = lambda db, user_id, message, *args, **kwargs: (
        searched.append((message, kwargs)) or {"type": "product_search"})

    use_case.process_text(db=None, user_id="u-ob", message="სხვა ბრენდის მოდელები მაჩვენეთ", locale="ka")

    message, kwargs = searched[0]
    assert message == "ფეხსაცმელი 36"                  # тот же поиск
    assert kwargs["exclude_brands"] == ["Adidas"]       # без уже показанных брендов
    assert kwargs["new_only"] is True and kwargs["max_price"] == 300   # условия разговора на месте


class _Stop(Exception):
    pass


def test_product_search_really_sends_exclude_brands(monkeypatch):
    captured = []

    def fake_search_products(db, request):
        captured.append(request)
        raise _Stop

    monkeypatch.setattr(chat_module, "search_products", fake_search_products)
    with pytest.raises(_Stop):
        ChatUseCase()._handle_product_search(None, "u-ob2", "ფეხსაცმელი 36", "ka", 5, 0,
                                             session=None, active_task=None, exclude_brands=["Adidas"])
    assert captured[0].exclude_brands == ["Adidas"]