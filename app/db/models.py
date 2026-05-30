from datetime import datetime, UTC

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=False)
    brand = Column(String, index=True, nullable=True)
    price = Column(Float, nullable=True)
    category_slug = Column(String, index=True, nullable=True)

    style_group = Column(String, index=True, nullable=True)
    sport_type = Column(String, index=True, nullable=True)
    usage_type = Column(String, index=True, nullable=True)
    model_family = Column(String, nullable=True)
    color = Column(String, nullable=True)

    size = Column(String, nullable=True)
    product_url = Column(String, unique=True, nullable=False)
    image_url = Column(String, nullable=True)


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