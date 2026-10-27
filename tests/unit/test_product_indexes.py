import pytest
from sqlalchemy import text

from app.db.session import engine, SessionLocal


TRIGRAM_INDEXES = {
    "ix_products_name_trgm",
    "ix_products_brand_trgm",
    "ix_products_sku_trgm",
}


@pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="pg_trgm indexes only apply to the Postgres (Neon) engine",
)
def test_trigram_indexes_exist_on_products_table():
    db = SessionLocal()
    try:
        result = db.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'products'")
        )
        existing_indexes = {row[0] for row in result}
    finally:
        db.close()

    missing = TRIGRAM_INDEXES - existing_indexes
    assert not missing, f"Missing trigram indexes: {missing}"