"""Исходная схема — ровно как в Neon на 02.11.2026 (замер information_schema + pg_indexes).

На существующей базе Neon НЕ выполняется: `alembic stamp 0001_baseline` только отмечает «уже так».
На новой пустой базе (сервер, проверка) создаёт всё с нуля.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 768   # текст: gemini-embedding-001; картинки: gemini-embedding-2 — обе по 768


def _id_index(table: str) -> None:
    op.create_index(f"ix_{table}_id", table, ["id"])


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- products (вручную позже добавлены regular_price 04.10 и is_new 21.10; индекса product_type нет — см. 0002)
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("brand", sa.String(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("category_slug", sa.String(), nullable=True),
        sa.Column("style_group", sa.String(), nullable=True),
        sa.Column("sport_type", sa.String(), nullable=True),
        sa.Column("usage_type", sa.String(), nullable=True),
        sa.Column("model_family", sa.String(), nullable=True),
        sa.Column("color", sa.String(), nullable=True),
        sa.Column("size", sa.String(), nullable=True),
        sa.Column("product_url", sa.String(), nullable=False),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("product_type", sa.String(), nullable=True),
        sa.Column("regular_price", sa.Float(), nullable=True),
        sa.Column("is_new", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("product_url", name="products_product_url_key"),
    )
    _id_index("products")
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)
    for column in ("brand", "category_slug", "style_group", "sport_type", "usage_type"):
        op.create_index(f"ix_products_{column}", "products", [column])
    for column in ("name", "brand", "sku"):
        op.create_index(f"ix_products_{column}_trgm", "products", [column],
                        postgresql_using="gin", postgresql_ops={column: "gin_trgm_ops"})

    # --- search_events
    op.create_table(
        "search_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("normalized_query", sa.String(), nullable=False),
        sa.Column("locale", sa.String(), nullable=False),
        sa.Column("intent", sa.String(), nullable=False),
        sa.Column("search_strategy", sa.String(), nullable=True),
        sa.Column("matched_by", sa.String(), nullable=True),
        sa.Column("results_count", sa.Integer(), nullable=False),
        sa.Column("top_sku", sa.String(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("ai_used", sa.Boolean(), nullable=False),
        sa.Column("ai_mode", sa.String(), nullable=True),
        sa.Column("ai_fallback_used", sa.Boolean(), nullable=False),
        sa.Column("ai_response_time_ms", sa.Float(), nullable=True),
        sa.Column("ai_error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    _id_index("search_events")
    op.create_index("ix_search_events_user_id", "search_events", ["user_id"])

    # --- conversation_sessions
    op.create_table(
        "conversation_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("last_query", sa.String(), nullable=True),
        sa.Column("last_detected_size", sa.String(), nullable=True),
        sa.Column("pending_clarification", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    _id_index("conversation_sessions")
    op.create_index("ix_conversation_sessions_user_id", "conversation_sessions", ["user_id"])

    # --- search_tasks
    op.create_table(
        "search_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("query", sa.String(), nullable=True),
        sa.Column("detected_brand", sa.String(), nullable=True),
        sa.Column("detected_size", sa.String(), nullable=True),
        sa.Column("current_step", sa.String(), nullable=True),
        sa.Column("completion_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    _id_index("search_tasks")
    op.create_index("ix_search_tasks_session_id", "search_tasks", ["session_id"])

    # --- scrape_runs
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("resumed", sa.Boolean(), nullable=False),
        *[sa.Column(name, sa.Integer(), nullable=False) for name in (
            "urls_total", "urls_failed", "created_count", "updated_count", "reactivated_count",
            "unchanged_count", "conflict_count", "deactivated_count")],
    )
    _id_index("scrape_runs")

    # --- product_changes
    op.create_table(
        "product_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("change_type", sa.String(), nullable=False),
        sa.Column("field", sa.String(), nullable=True),
        sa.Column("old_value", sa.String(), nullable=True),
        sa.Column("new_value", sa.String(), nullable=True),
        sa.Column("old_price", sa.Float(), nullable=True),
        sa.Column("new_price", sa.Float(), nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
    )
    _id_index("product_changes")
    for column in ("run_id", "sku", "change_type", "changed_at"):
        op.create_index(f"ix_product_changes_{column}", "product_changes", [column])

    # --- векторы (нет в models.py; пишут ingestion/build_embeddings.py и build_image_embeddings.py)
    op.execute(f"""
        CREATE TABLE product_embeddings (
            page_url   TEXT PRIMARY KEY,
            text_hash  TEXT NOT NULL,
            model      TEXT NOT NULL,
            embedding  vector({EMBEDDING_DIM}) NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        )""")
    op.execute("CREATE INDEX ix_product_embeddings_hnsw ON product_embeddings "
               "USING hnsw (embedding vector_cosine_ops)")
    op.execute(f"""
        CREATE TABLE product_image_embeddings (
            page_url   TEXT PRIMARY KEY,
            image_url  TEXT NOT NULL,
            model      TEXT NOT NULL,
            embedding  vector({EMBEDDING_DIM}) NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )""")
    op.execute("CREATE INDEX ix_product_image_embeddings_hnsw ON product_image_embeddings "
               "USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    # Удаляет ВСЁ (вместе с данными). Расширения pg_trgm / vector не трогаем.
    for table in ("product_image_embeddings", "product_embeddings", "product_changes", "scrape_runs",
                  "search_tasks", "conversation_sessions", "search_events", "products"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")