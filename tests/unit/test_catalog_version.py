"""03.11: кэш поиска по «номеру дня» каталога — после обновления каталога поиск идёт в базу заново,
пока номер тот же — берёт из кэша. Без Redis и базы (память, репозиторий подменён)."""
from types import SimpleNamespace

from app.schemas.search_request import SearchRequest
from app.services import cache_service, product_service


def _product(product_id):
    return SimpleNamespace(
        id=product_id, name=f"Nike Runner {product_id}", brand="nike", sku=f"NK-{product_id}", price=100.0,
        regular_price=None, size="42", category_slug=None, product_type=None, style_group=None, sport_type=None,
        usage_type=None, model_family=None, color=None, is_active=True, is_new=False, image_url=None,
        product_url=f"https://topsport.ge/ka/product/nike-runner-{product_id}",
    )


def _count_db_calls(monkeypatch):
    calls = []

    def fake_get_products_by_query(db, q, **kwargs):
        calls.append(q)
        return [_product(1), _product(2)], 2

    monkeypatch.setattr(product_service, "get_products_by_query", fake_get_products_by_query)
    return calls


def _search():
    return product_service.search_products(db=None, request=SearchRequest(raw_query="nike", limit=5, offset=0))


def test_same_catalog_version_uses_cache_new_version_goes_to_db(monkeypatch):
    cache_service.clear()
    calls = _count_db_calls(monkeypatch)

    _search()
    _search()
    assert len(calls) == 1                     # второй раз — из кэша, в базу не ходили

    cache_service.bump_catalog_version()       # скрапер закончил → новый номер дня
    _search()
    assert len(calls) == 2                     # новый номер → свежие данные из базы


def test_conversation_survives_catalog_update():
    cache_service.clear()
    cache_service.set("chat:state:u1", {"size": "36"}, ttl=1800)
    cache_service.bump_catalog_version()
    assert cache_service.get("chat:state:u1") == {"size": "36"}   # номер дня не трогает разговоры


def test_version_default_and_bump():
    cache_service.clear()
    assert cache_service.catalog_version() == "0"                  # номера нет → "0", поиск работает
    first = cache_service.bump_catalog_version()
    second = cache_service.bump_catalog_version()
    assert cache_service.catalog_version() == second != first


def test_ttl_day_in_redis_short_in_memory(monkeypatch):
    assert cache_service.search_cache_ttl() == 60                   # тесты / локально — память
    monkeypatch.setattr(cache_service, "CACHE_BACKEND", "redis")
    assert cache_service.search_cache_ttl() == 24 * 3600