"""Database-unavailable behavior — deliberately points at an unreachable
port, so this runs without any real PostgreSQL instance."""

from __future__ import annotations

from sqlalchemy import create_engine

import app.database.session as session_module
from app.monitoring.health import check_readiness


def test_is_database_available_false_for_unreachable_host(monkeypatch):
    bad_engine = create_engine("postgresql+psycopg://user:pass@127.0.0.1:1/nonexistent", pool_pre_ping=True)
    monkeypatch.setattr(session_module, "engine", bad_engine)
    assert session_module.is_database_available() is False


def test_readiness_reflects_database_unavailable(monkeypatch):
    monkeypatch.setattr("app.monitoring.health.is_database_available", lambda: False)
    status = check_readiness()
    assert status.ready is False
    assert status.database_available is False


def test_readiness_reflects_database_available(monkeypatch):
    monkeypatch.setattr("app.monitoring.health.is_database_available", lambda: True)
    status = check_readiness()
    assert status.ready is True
