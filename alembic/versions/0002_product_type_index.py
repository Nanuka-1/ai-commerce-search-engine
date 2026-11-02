"""Индекс products.product_type — в models.py он есть (index=True), а в Neon его нет:
колонку добавляли вручную, а create_all индексы к существующей таблице не добавляет.
Первая НАСТОЯЩАЯ миграция: выполняется на Neon командой `alembic upgrade head`.

Revision ID: 0002_product_type_index
Revises: 0001_baseline
Create Date: 2026-11-02
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_product_type_index"
down_revision: Union[str, Sequence[str], None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_products_product_type", "products", ["product_type"])


def downgrade() -> None:
    op.drop_index("ix_products_product_type", table_name="products")