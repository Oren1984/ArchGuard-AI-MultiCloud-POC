"""Secret redaction in responses, and .env.example contains no real secrets."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]

_FORBIDDEN_MARKERS = ("sk-", "AKIA", "-----BEGIN")


def test_env_example_has_no_real_looking_secrets():
    content = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for marker in _FORBIDDEN_MARKERS:
        assert marker not in content, f"Found suspicious marker '{marker}' in .env.example"
    # Passwords in the template must be obvious placeholders, not real-looking values.
    assert "changeme-local-only" in content


def test_unhandled_error_response_never_leaks_internal_detail(client, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("db_password=super-secret-value connection failed")

    monkeypatch.setattr("app.repositories.postgres_repositories.SqlAlchemyEventRepository.get", _boom)
    import uuid

    from fastapi.testclient import TestClient

    # A bare-Exception handler attaches to Starlette's outermost
    # ServerErrorMiddleware, which by design still re-raises to the caller
    # when raise_server_exceptions=True (TestClient's default) even though
    # it already sent our JSON response — disable that here to assert on
    # the actual HTTP response our handler produced, matching real runtime
    # behavior (uvicorn never re-raises to the client).
    with TestClient(client.app, raise_server_exceptions=False) as non_raising_client:
        resp = non_raising_client.get(f"/events/{uuid.uuid4()}")

    assert resp.status_code == 500
    body = resp.json()
    assert "super-secret-value" not in resp.text
    assert body["error"] == "internal_error"
    assert "correlation_id" in body


def test_404_response_does_not_echo_database_details(client):
    import uuid

    resp = client.get(f"/events/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert "postgresql" not in resp.text.lower()
    assert "sqlalchemy" not in resp.text.lower()
