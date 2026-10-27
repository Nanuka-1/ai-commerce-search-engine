"""13.10: вопрос только про цвет → не ищем (цвет в базе почти не размечен), ведём на страницу товара."""
import pytest

from app.services.translations import translate
from app.use_cases.chat_use_case import ChatUseCase, is_color_question


@pytest.mark.parametrize("message", ["და შავ ფერში თუ გაქვთ ?", "თეთრი გაქვთ?", "in black?", "other colors?"])
def test_color_only_questions(message):
    assert is_color_question(message) is True


@pytest.mark.parametrize("message", ["შავი სარბენი 42", "თეთრი კედები", "black shoes", "და 43?", "კიდევ 5",
                                     "ფასდაკლება"])
def test_not_color_questions(message):
    # свой товар, размер или вообще не про цвет → обычный путь (поиск / ИИ)
    assert is_color_question(message) is False


def test_color_question_in_conversation_points_to_product_page():
    response = ChatUseCase()._handle_color_question("u7", "და შავ ფერში თუ გაქვთ ?", "ka", in_conversation=True)
    assert response["type"] == "color_question"
    assert response["message"] == translate("color_on_product_page", "ka")


def test_color_question_without_conversation_is_not_intercepted():
    assert ChatUseCase()._handle_color_question("u7", "შავი", "ka", in_conversation=False) is None