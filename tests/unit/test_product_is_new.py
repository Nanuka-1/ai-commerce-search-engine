"""21.10: у товара есть признак «новинка», по умолчанию — нет."""
from app.db.models import Product


def test_product_has_is_new_column_defaulting_to_false():
    column = Product.__table__.c.is_new
    assert column.nullable is False
    assert column.default.arg is False