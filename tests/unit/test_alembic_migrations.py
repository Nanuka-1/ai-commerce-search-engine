"""02.11: миграции Alembic — без базы: Alembic печатает SQL (`--sql`), проверяем его текст.
Настоящая проверка на пустой базе Postgres — вручную (шаг 3) и потом в CI."""
import io
import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.models import Base

ROOT = Path(__file__).resolve().parents[2]
VECTOR_TABLES = {"product_embeddings", "product_image_embeddings"}


def _config(buffer=None) -> Config:
    config = Config(str(ROOT / "alembic.ini"), output_buffer=buffer)
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", "postgresql://user@localhost/offline")   # база не нужна
    return config


def _upgrade_sql() -> str:
    buffer = io.StringIO()
    command.upgrade(_config(buffer), "head", sql=True)
    return buffer.getvalue()


def test_one_straight_chain_of_migrations():
    scripts = ScriptDirectory.from_config(_config())
    assert scripts.get_heads() == ["0002_product_type_index"]          # одна «голова» — без развилок
    chain = [rev.revision for rev in scripts.walk_revisions()]
    assert chain == ["0002_product_type_index", "0001_baseline"]
    assert all(len(rev) <= 32 for rev in chain)                       # alembic_version.version_num — VARCHAR(32)


def test_upgrade_creates_every_table_from_models_and_vector_tables():
    sql = _upgrade_sql()
    for table in set(Base.metadata.tables) | VECTOR_TABLES:
        assert f"CREATE TABLE {table} " in sql, table
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in sql


def test_upgrade_creates_every_index_from_models():
    sql = _upgrade_sql()
    for table in Base.metadata.tables.values():
        for index in table.indexes:
            assert f"CREATE {'UNIQUE ' if index.unique else ''}INDEX {index.name} " in sql, index.name
        for column in table.columns:
            if column.index and not column.unique:
                assert f"INDEX ix_{table.name}_{column.name} " in sql, column.name


def test_every_model_column_is_created():
    sql = _upgrade_sql()
    for table in Base.metadata.tables.values():
        block = sql.split(f"CREATE TABLE {table.name} ", 1)[1].split(";", 1)[0]
        for column in table.columns:
            assert re.search(rf"[\s(]{column.name} ", block), f"{table.name}.{column.name}"