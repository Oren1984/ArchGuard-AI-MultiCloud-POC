"""Shared pytest fixtures.

DB-backed tests (integration/api/security/e2e) run against a real
PostgreSQL database — never SQLite — per project policy. They connect to
TEST_DATABASE_URL (default: a dedicated `archguard_test` database on
localhost, created by scripts/init-test-db.sql) and skip cleanly if it is
unreachable, so unit tests still run without Docker/Postgres present.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# .env points DATABASE_URL at the docker-network hostname "db" (correct for
# the app container). Tests normally run on the host, where that hostname
# doesn't resolve, so override to localhost *before* any app module import
# triggers app.database.session's module-level engine creation. A real
# pre-set DATABASE_URL (e.g. running tests inside the app container) wins.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://archguard:changeme-local-only@localhost:5432/archguard"
)

from app.database import models  # noqa: F401,E402 — registers tables on Base.metadata
from app.database.base import Base  # noqa: E402

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://archguard:changeme-local-only@localhost:5432/archguard_test",
)


def _postgres_available() -> bool:
    try:
        engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


POSTGRES_AVAILABLE = _postgres_available()


@pytest.fixture(scope="session")
def test_engine():
    if not POSTGRES_AVAILABLE:
        pytest.skip(f"PostgreSQL not reachable at {TEST_DATABASE_URL}; skipping DB-backed test.")
    engine = create_engine(TEST_DATABASE_URL, future=True)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, future=True, autoflush=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        # A flushed IntegrityError already deactivates the DBAPI transaction
        # internally — only roll back if it's still active, to avoid a
        # harmless-but-noisy "transaction already deassociated" SAWarning.
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session):
    from app.api.dependencies import get_db_session
    from app.main import app

    def _override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = _override_get_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
