"""20.10: «ещё / другие» пишем в аналитику отдельно — их ноль не ломает статистику нулевых запросов."""
from app.use_cases.chat_use_case import search_log_intent


def test_normal_search_is_product_search():
    assert search_log_intent(None) == "product_search"
    assert search_log_intent(set()) == "product_search"


def test_more_request_is_logged_separately():
    assert search_log_intent({"https://topsport.ge/ka/product/a"}) == "product_search_more"