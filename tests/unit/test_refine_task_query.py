"""15.10: уточнение к прошлому запросу не дублирует слова.
Баг: клиент повторил «ქალის ჯემპრი S» → поиск получил «ქალის ჯემპრი ქალის ჯემპრი S»
(другие карточки + промах кэша → лишний вызов Gemini)."""
from app.services.conversation_resolution_service import refine_task_query


def test_same_message_again_keeps_query():
    assert refine_task_query("ქალის ჯემპრი S", "ქალის ჯემპრი S") == "ქალის ჯემპრი S"


def test_new_size_replaces_old_size():
    assert refine_task_query("სარბენი ფეხსაცმელი 42", "43") == "სარბენი ფეხსაცმელი 43"


def test_only_new_words_are_added_case_insensitive():
    assert refine_task_query("nike 42", "Nike air max 42") == "nike air max 42"
    assert refine_task_query("ქალის ჯემპრი S", "შავი შავი") == "ქალის ჯემპრი S შავი"