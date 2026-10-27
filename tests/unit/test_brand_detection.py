import pytest

from app.services.query_parser_service import extract_brand_from_query


@pytest.mark.parametrize("query, expected", [
    ("crocs 42", "crocs"),                       # бренд, которого раньше не было в списке
    ("კროქსი 42", "crocs"),                      # основное грузинское написание
    ("კროკსი 42", "crocs"),                      # вариант с одной буквой разницы — ловит _is_close
    ("speedo", "speedo"),
    ("new balance 42", "new balance"),           # нет в каталоге, но распознаём -> brand_fallback
    ("Nike Air Max 90 42", "nike"),              # как раньше
    ("შავი nike 42", "nike"),
    ("ნაიკი 42", "nike"),                        # грузинское написание
    ("ნაიკის ბოტასი 42", "nike"),                 # падежное окончание
    ("ადიდასის ჯემპრი", "adidas"),
    ("nkie 42", "nike"),                         # перестановка букв
    ("pmua 41", "puma"),
    ("adidsa samba 40", "adidas"),
    ("addidas 40", "adidas"),                    # лишняя буква
    ("under armor shorts L", "under armour"),    # американское написание, два слова
])
def test_extract_brand_recognizes_spellings_and_typos(query, expected):
    assert extract_brand_from_query(query) == expected


@pytest.mark.parametrize("query", [
    "nice shoes 42",                             # nice ≠ nike: замена буквы в коротком слове не считается
    "pegasus 41",
    "samba 40",
    "running shoes 42",
    "warm jacket M",
    "მამაკაცის სპორტული ფეხსაცმელი 43",
    "ქალის ჯემპრი S",
    "ბავშვის ბოტასი 30",
    "31241503",
])
def test_extract_brand_no_false_positives(query):
    assert extract_brand_from_query(query) is None