"""20.10 (этап 2, экзамен): формы слов пола → категория; ИИ не называет товары «новой коллекцией» без данных."""
import pytest

from app.services.intent_router import extract_category_from_query
from app.services.llm_text_service import validate_llm_text


@pytest.mark.parametrize("message, expected", [
    ("ბიჭის ფეხსაცმელი 36", "kids"),
    ("გოგოს კედები 30", "kids"),
    ("ბავშვისთვის ქურთუკი", "kids"),
    ("ნაიკის ფეხსაცმელი 36 ზომა ქალისთვის", "women"),
    ("კაცის სარბენი 42", "men"),
    ("მამაკაცისთვის შორტი L", "men"),
    ("ქალის ჯემპრი S", "women"),          # старое не сломали
    ("nike 42", None),
])
def test_gender_word_forms(message, expected):
    assert extract_category_from_query(message) == expected


FACTS = "CUSTOMER MESSAGE: ახალი კოლექცია რა გაქვთ\nBASE MESSAGE: აი 5 ვარიანტი\nPRODUCTS FOUND: 5"


def test_new_collection_claim_rejected():
    ok, reason = validate_llm_text("კი, ახალი კოლექციიდან ბევრი ვარიანტი ვიპოვე 👟", FACTS, "ka")
    assert (ok, reason) == (False, "new_claim")


def test_english_new_arrivals_rejected():
    ok, reason = validate_llm_text("Here are our new arrivals for you 👟", FACTS, "en")
    assert (ok, reason) == (False, "new_claim")


def test_normal_answer_still_ok():
    ok, _ = validate_llm_text("კი, ვიპოვე შესაბამისი ვარიანტები 👟", FACTS, "ka")
    assert ok


def test_new_claim_allowed_when_search_confirms():
    facts = FACTS + "\nNEW COLLECTION: yes"
    ok, _ = validate_llm_text("კი, ახალი კოლექციიდან ვიპოვე ვარიანტები 👟", facts, "ka")
    assert ok