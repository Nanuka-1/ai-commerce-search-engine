from datetime import datetime, UTC

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Index, false
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=False)
    brand = Column(String, index=True, nullable=True)
    price = Column(Float, nullable=True)
    regular_price = Column(Float, nullable=True)
    category_slug = Column(String, index=True, nullable=True)
    product_type = Column(String, index=True, nullable=True)

    style_group = Column(String, index=True, nullable=True)
    sport_type = Column(String, index=True, nullable=True)
    usage_type = Column(String, index=True, nullable=True)
    model_family = Column(String, nullable=True)
    color = Column(String, nullable=True)

    size = Column(String, nullable=True)
    product_url = Column(String, unique=True, nullable=False)
    image_url = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    # 21.10: «ახალი კოლექცია» — список новинок магазина (фильтр на /ka/products), ставит ingestion/collect_new_products.py
    is_new = Column(Boolean, nullable=False, default=False, server_default=false())

    __table_args__ = (
        Index("ix_products_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
        Index("ix_products_brand_trgm", "brand", postgresql_using="gin", postgresql_ops={"brand": "gin_trgm_ops"}),
        Index("ix_products_sku_trgm", "sku", postgresql_using="gin", postgresql_ops={"sku": "gin_trgm_ops"}),
    )


class SearchEvent(Base):
    __tablename__ = "search_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    query = Column(String, nullable=False)
    normalized_query = Column(String, nullable=False)
    locale = Column(String, nullable=False, default="en")
    intent = Column(String, nullable=False)
    search_strategy = Column(String, nullable=True)
    matched_by = Column(String, nullable=True)
    results_count = Column(Integer, nullable=False, default=0)
    top_sku = Column(String, nullable=True)
    success = Column(Boolean, nullable=False, default=False)

    ai_used = Column(Boolean, nullable=False, default=False)
    ai_mode = Column(String, nullable=True)
    ai_fallback_used = Column(Boolean, nullable=False, default=False)
    ai_response_time_ms = Column(Float, nullable=True)
    ai_error = Column(String, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(String, index=True, nullable=False)

    status = Column(String, nullable=False, default="active")

    last_query = Column(String, nullable=True)

    last_detected_size = Column(String, nullable=True)

    pending_clarification = Column(String, nullable=True)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

class SearchTask(Base):
    __tablename__ = "search_tasks"

    id = Column(Integer, primary_key=True, index=True)

    session_id = Column(Integer, nullable=False, index=True)

    status = Column(String, nullable=False, default="active")

    query = Column(String, nullable=True)

    detected_brand = Column(String, nullable=True)

    detected_size = Column(String, nullable=True)

    current_step = Column(String, nullable=True)

    completion_reason = Column(String, nullable=True)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    finished_at = Column(DateTime, nullable=True)
    resumed = Column(Boolean, nullable=False, default=False)

    urls_total = Column(Integer, nullable=False, default=0)
    urls_failed = Column(Integer, nullable=False, default=0)
    created_count = Column(Integer, nullable=False, default=0)
    updated_count = Column(Integer, nullable=False, default=0)
    reactivated_count = Column(Integer, nullable=False, default=0)
    unchanged_count = Column(Integer, nullable=False, default=0)
    conflict_count = Column(Integer, nullable=False, default=0)
    deactivated_count = Column(Integer, nullable=False, default=0)


class ProductChange(Base):
    __tablename__ = "product_changes"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, index=True, nullable=True)
    sku = Column(String, index=True, nullable=False)
    change_type = Column(String, index=True, nullable=False)
    field = Column(String, nullable=True)
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    old_price = Column(Float, nullable=True)
    new_price = Column(Float, nullable=True)
    changed_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True)