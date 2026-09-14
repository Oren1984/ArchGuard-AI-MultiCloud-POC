"""Verifies Alembic migrations against a real, disposable PostgreSQL
database (created/dropped via the admin connection) — fully isolated from
the shared `test_engine` fixture so migration up/down doesn't interfere
with other integration tests' schema state.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

from tests.conftest import POSTGRES_AVAILABLE, TEST_DATABASE_URL

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_TEST_DB = "archguard_migrations_test"

EXPECTED_TABLES = {
    "operational_events",
    "risk_assessments",
    "ai_recommendations",
    "evaluation_results",
    "approval_decisions",
    "audit_logs",
    "kill_switch_events",
    "provider_eligibility_records",
    "alembic_version",
}


def _url_for(dbname: str) -> str:
    # str(url) masks the password by default — must render it explicitly or
    # the subprocess alembic invocation gets a literal "***" as the password.
    return make_url(TEST_DATABASE_URL).set(database=dbname).render_as_string(hide_password=False)


def _admin_conninfo() -> str:
    url = make_url(TEST_DATABASE_URL)
    return f"host={url.host} port={url.port} user={url.username} password={url.password} dbname=postgres"


@pytest.fixture()
def migration_database_url():
    if not POSTGRES_AVAILABLE:
        pytest.skip(f"PostgreSQL not reachable at {TEST_DATABASE_URL}; skipping migration test.")
    with psycopg.connect(_admin_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {MIGRATION_TEST_DB}")
        cur.execute(f"CREATE DATABASE {MIGRATION_TEST_DB}")
    yield _url_for(MIGRATION_TEST_DB)
    with psycopg.connect(_admin_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {MIGRATION_TEST_DB}")


def _run_alembic(*args: str, database_url: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": database_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_alembic_upgrade_head_creates_all_tables(migration_database_url):
    result = _run_alembic("upgrade", "head", database_url=migration_database_url)
    assert result.returncode == 0, result.stderr

    engine = create_engine(migration_database_url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert EXPECTED_TABLES.issubset(tables)


def test_alembic_downgrade_base_removes_all_tables(migration_database_url):
    up = _run_alembic("upgrade", "head", database_url=migration_database_url)
    assert up.returncode == 0, up.stderr

    down = _run_alembic("downgrade", "base", database_url=migration_database_url)
    assert down.returncode == 0, down.stderr

    engine = create_engine(migration_database_url)
    remaining = set(inspect(engine).get_table_names()) - {"alembic_version"}
    engine.dispose()
    assert remaining == set()
