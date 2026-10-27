from types import SimpleNamespace

import pytest

from app.services.llm_text_service import (
    build_facts, build_prompt, should_use_llm, validate_llm_text,
)

PEGASUS = {"name": "Nike Air Zoom Pegasus 41", "brand": "Nike", "sizes": ["42", "43"],
           "price": 318.0, "regular_price": 455.0, "product_url": "https://topsport.ge/ka/product/p"}


def _context(**overrides):
    values = dict(items=[PEGASUS], total_count=1, result_mode="normal")
    values.update(overrides)
    return SimpleNamespace(**values)


BASE = "თქვენი ზომა 42 ვიპოვე! კონკრეტულ ფილიალში მარაგი გადაამოწმეთ პროდუქტის გვერდზე."
FACTS = build_facts(_context(), BASE, "pegasus 42")


def test_should_use_llm_only_with_products_and_not_for_size_question():
    assert should_use_llm(_context())
    assert not should_use_llm(_context(items=[], total_count=0))
    assert not should_use_llm(_context(result_mode="need_size"))
    assert not should_use_llm(None)


def test_facts_contain_only_search_data_and_discount():
    assert "CUSTOMER MESSAGE: pegasus 42" in FACTS
    assert BASE in FACTS
    assert "Nike Air Zoom Pegasus 41; brand: Nike; sizes: 42, 43; price: 318 GEL" in FACTS
    assert "regular price: 455 GEL, discount: 30%" in FACTS
    assert "https://" not in FACTS                     # ссылки модели не даём


def test_prompt_language_and_rules():
    system, user = build_prompt(_context(), BASE, "pegasus 42", "ka")
    assert "Write ONLY in Georgian" in system and "Never invent" in system
    assert user == FACTS


@pytest.mark.parametrize("text", [
    "კარგი ამბავია — თქვენი ზომა 42 ვიპოვეთ 👟 Nike Pegasus 41 ახლა 30%-იანი ფასდაკლებით არის!",
    "თქვენი ზომა ვიპოვეთ! მარაგი ფილიალში გადაამოწმეთ საიტზე ✅",
])
def test_valid_georgian_text_passes(text):
    assert validate_llm_text(text, FACTS, "ka") == (True, "ok")


@pytest.mark.parametrize("text, reason", [
    ("", "empty"),
    ("ფასი მხოლოდ 199 ლარია!", "unknown_numbers:199"),              # выдуманная цена
    ("ნახეთ აქ: https://topsport.ge/ka/product/p", "link"),
    ("ვიპოვეთ! 👟🔥✅", "too_many_emoji"),
    ("We found your size 42!", "wrong_language"),                    # клиент грузинский
    ("ა" * 401, "too_long"),
])
def test_invalid_text_is_rejected(text, reason):
    assert validate_llm_text(text, FACTS, "ka") == (False, reason)


def test_english_must_not_contain_georgian():
    assert validate_llm_text("Great news — size 42 is found 👟", FACTS, "en") == (True, "ok")
    assert validate_llm_text("ზომა 42 ვიპოვე, გთხოვთ გადაამოწმოთ", FACTS, "en") == (False, "wrong_language")


# --- 09.10: правки после живой проверки 3.7d ---
from app.services.llm_text_service import clean_llm_text


@pytest.mark.parametrize("raw, expected", [
    ("მოგესალმებით! თქვენი ზომა 42 ვიპოვე 👟", "თქვენი ზომა 42 ვიპოვე 👟"),
    ("Hello! Welcome to TopSport. We found your size 42!", "We found your size 42!"),
    ("გამარჯობა, ზომა ვიპოვე", "ზომა ვიპოვე"),
    ("თქვენი ზომა 42 ვიპოვე", "თქვენი ზომა 42 ვიპოვე"),            # без приветствия — не трогаем
])
def test_clean_llm_text_removes_greeting(raw, expected):
    assert clean_llm_text(raw) == expected


def test_more_than_three_sentences_rejected():
    text = "ზომა 42 ვიპოვე. მარაგი გადაამოწმეთ. შეუკვეთეთ საიტზე. დააზუსტეთ მოდელი."
    assert validate_llm_text(text, FACTS, "ka") == (False, "too_many_sentences")
    assert validate_llm_text("ზომა 42 ვიპოვე 👟. მარაგი გადაამოწმეთ საიტზე ✅.", FACTS, "ka") == (True, "ok")


def test_prompt_forbids_greeting_and_sets_emoji_by_type():
    system, _ = build_prompt(_context(), BASE, "pegasus 42", "ka")
    assert "Do NOT greet" in system and "🧥 jackets" in system and "At most 3" in system


# --- 09.10: честность (3.7d, второй прогон) ---
@pytest.mark.parametrize("text", [
    "თქვენი ზომა 42 ვიპოვე და ამ ზომაში 1 შესაბამისი პროდუქტი გვაქვს! 👟",
    "Pegasus მარაგშია ✅",
])
def test_stock_promise_rejected_georgian(text):
    assert validate_llm_text(text, FACTS, "ka") == (False, "stock_promise")


def test_stock_promise_rejected_english_but_check_stock_allowed():
    assert validate_llm_text("We have your size 42 👟", FACTS, "en") == (False, "stock_promise")
    assert validate_llm_text("It is in stock!", FACTS, "en") == (False, "stock_promise")
    ok = "We found your size 42! Please check stock in a specific store on the product page."
    assert validate_llm_text(ok, FACTS, "en") == (True, "ok")


def test_prompt_forbids_stock_words_and_invented_qualities():
    system, _ = build_prompt(_context(), BASE, "warm jacket M", "en")
    assert "Never say \"we have\"" in system and "Do not attribute qualities" in system


def test_english_text_may_quote_georgian_product_name():
    # 09.10: en-ответ цитировал грузинское название товара из каталога → ложное wrong_language
    text = "I found your size 42, for example Nike მამაკაცის ქურთუკი 🧥. Please check stock in a store."
    assert validate_llm_text(text, FACTS, "en") == (True, "ok")


def test_prompt_insists_on_language_even_with_georgian_names():
    system, _ = build_prompt(_context(), BASE, "nike 42", "en")
    assert "Product names in the facts may be in Georgian — still answer ONLY in English" in system