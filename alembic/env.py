"""
02.11: Alembic берёт адрес базы из DATABASE_URL (Doppler), схему — из app/db/models.py.

Важно:
- Импортируем ТОЛЬКО app.db.models (не session.py — там подключение к базе при импорте).
- Таблицы векторов (product_embeddings, product_image_embeddings) не описаны в models.py — с ними работают
  скрипты сырым SQL. Создаёт их миграция 0001; для сравнения «models.py ↔ база» (`alembic check`) они
  исключены, иначе Alembic предложил бы их УДАЛИТЬ.
"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)   # не глушить логи приложения / тестов

target_metadata = Base.metadata

# таблицы, которых нет в models.py, но они наши (создаёт 0001_baseline)
RAW_SQL_TABLES = {"product_embeddings", "product_image_embeddings"}


def include_name(name, type_, parent_names):
    """Таблицы векторов не сравниваем с models.py (и даже не читаем их структуру)."""
    if type_ == "table":
        return name not in RAW_SQL_TABLES
    return True


def database_url() -> str:
    url = config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL не задан — запускайте через: doppler run -- alembic …")
    return url


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql` — только напечатать SQL, без подключения к базе."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        {"sqlalchemy.url": database_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_name=include_name)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()