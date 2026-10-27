import json
from pathlib import Path

import pytest

from app.services.store_info_service import build_store_info_response, detect_store_topic, load_store_info

INFO = {
    "links": {"terms": {"ka": "https://t/ka", "en": "https://t/en"}, "stores": {"ka": "https://s/ka", "en": "https://s/en"}},
    "phone": "032 205 21 20", "email": "info@topsport.ge",
    "answers": {
        "delivery": {"ka": "მიწოდება 3–5 დღე, 5 ლარი. {terms}", "en": "Delivery 3–5 days, 5 GEL. {terms}"},
        "returns": {"ka": "დაბრუნება 14 დღე. {terms}", "en": "Returns 14 days. {terms}"},
        "stores": {"ka": "მაღაზიები: {stores}, {phone}", "en": "Stores: {stores}, {phone}"},
    },
}


@pytest.mark.parametrize("message, topic", [
    ("მიტანა გაქვთ თბილისში?", "delivery"),
    ("რამდენ დღეში მოდის მიწოდება", "delivery"),
    ("do you deliver to Batumi?", "delivery"),
    ("შეიძლება გაცვლა ზომის?", "returns"),
    ("how can I return shoes", "returns"),
    ("დაბრუნების მიწოდება ვინ იხდის", "returns"),            # возврат важнее доставки
    ("სად ხართ ბათუმში?", "stores"),
    ("მაღაზიის მისამართი", "stores"),
    ("მაღაზიის ტელეფონი", "contact"),                       # контакт важнее магазина
    ("ბარათით გადახდა შეიძლება?", "payment"),
    ("სარბენი ფეხსაცმელი 42", None),                         # обычный поиск
    ("nike 42", None),
])
def test_detect_store_topic(message, topic):
    assert detect_store_topic(message) == topic


def test_answer_from_config_with_links():
    response = build_store_info_response("მიტანა გაქვთ?", "u1", "ka", INFO)
    assert response["type"] == "store_info" and response["data"]["topic"] == "delivery"
    assert response["message"] == "მიწოდება 3–5 დღე, 5 ლარი. https://t/ka"


def test_english_and_placeholders():
    response = build_store_info_response("where are you located? store address", "u1", "en", INFO)
    assert response["message"] == "Stores: https://s/en, 032 205 21 20"


def test_unknown_topic_or_missing_answer_falls_back_to_search():
    assert build_store_info_response("nike 42", "u1", "ka", INFO) is None
    assert build_store_info_response("ბარათით გადახდა?", "u1", "ka", INFO) is None   # нет ответа payment в INFO


def test_real_config_file_is_valid():
    info = load_store_info(Path(__file__).resolve().parents[2] / "app" / "config" / "store_info.json")
    assert info is not None
    for topic in ("delivery", "returns", "payment", "stores", "contact"):
        assert set(info["answers"][topic]) == {"ka", "en"}


def test_size_number_is_not_contact_question():
    assert detect_store_topic("ზომის ნომერი 42 მინდა") is None      # "ნომერი" = номер размера, не телефон