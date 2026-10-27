import pytest

from app.db.session import engine


@pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="Pool tuning only applies to the Postgres (Neon) engine, not the SQLite fallback",
)
def test_engine_has_pool_pre_ping_enabled():
    assert engine.pool._pre_ping is True


@pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="Pool tuning only applies to the Postgres (Neon) engine, not the SQLite fallback",
)
def test_engine_has_pool_recycle_configured():
    assert engine.pool._recycle == 300


@pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="Pool tuning only applies to the Postgres (Neon) engine, not the SQLite fallback",
)
def test_engine_pool_size_configured():
    assert engine.pool.size() == 5