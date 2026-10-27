"""13.10: «наличие в филиале — на странице товара» и призыв заказать — один раз, дальше коротко «ზომა 36 ✅»."""
from types import SimpleNamespace

from app.services.response_builder import AVAILABILITY_CTA, build_response, build_site_search_url, georgian_genitive
from app.services.translations import translate


def _context():
    return SimpleNamespace(
        items=[{"name": "Nike", "product_url": "https://topsport.ge/ka/product/a?size=36"}],
        total_count=1, offset=0, query="ბავშვის ფეხსაცმელი 36", matched_by="query", search_strategy="broad",
        detected_size="36", model_hint=None, detected_color=None, result_mode="found",
    )


def test_first_answer_has_stock_hint_and_cta():
    message = build_response(_context(), "u", "product_search", "ka")["message"]
    assert message.startswith(translate("search_size_available", "ka").format(size="36"))
    assert message.endswith(AVAILABILITY_CTA["ka"])


def test_next_answers_are_short():
    message = build_response(_context(), "u", "product_search", "ka", stock_hint=False)["message"]
    assert message.startswith("ზომა 36 ✅")
    assert AVAILABILITY_CTA["ka"] not in message
    assert "მაღაზიებში შემოწმება" not in message



def test_site_link_keeps_only_words_from_found_names():
    # 13.10: сайт ищет по ВСЕМ словам → «ბიჭის» (нет в названиях) давало пустую страницу
    url = build_site_search_url("ბავშვის ბიჭის ფეხსაცმელი 36", "36", "ka",
                                ["Adidas ბავშვის სპორტული ფეხსაცმელი", "Nike ბავშვის ბოტასი"])
    assert "term=%E1%83%91%E1%83%90%E1%83%95%E1%83%A8%E1%83%95%E1%83%98%E1%83%A1+" in url   # «ბავშვის+…»
    assert "ბიჭის" not in url and "%E1%83%91%E1%83%98%E1%83%AD" not in url
    # без найденных товаров — как раньше (запрос без размера)
    assert build_site_search_url("adidas samba 46", "46", "en").endswith("term=adidas+samba&search_type=name")


def test_need_model_text_only_first_time():
    context = _context()
    context.total_count, context.result_mode = 40, "need_model"
    context.items = context.items * 5
    first = build_response(context, "u", "product_search", "ka")["message"]
    later = build_response(context, "u", "product_search", "ka", stock_hint=False)["message"]
    assert "SKU" in first                                        # «уточните модель — SKU…» — один раз
    assert later == "ზომა 36 ✅ აი 5 ვარიანტი 👇"



def test_georgian_genitive_of_model_names():
    # 13.10: «„samba“-ის» — неверное окончание; на гласную → -ს, на согласную → -ის
    assert georgian_genitive("samba") == "Samba-ს"
    assert georgian_genitive("pegasus") == "Pegasus-ის"
    assert georgian_genitive("air max") == "Air Max-ის"
    assert georgian_genitive("nmd") == "NMD-ის"
    assert georgian_genitive(None) == ""


def test_need_size_message_uses_correct_ending():
    context = _context()
    context.result_mode, context.model_hint, context.detected_size = "need_size", "samba", None
    message = build_response(context, "u", "product_search", "ka")["message"]
    assert message.startswith("ვიპოვე Samba-ს მოდელები")