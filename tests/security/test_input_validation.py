"""Security-focused input validation: oversized payloads, injection-shaped
strings, and identity-header format enforcement."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

ACTOR = {"X-ArchGuard-Actor": "operator:test"}

BASE_EVENT = {
    "event_type": "performance_degradation",
    "source": "datadog",
    "description": "desc",
    "affected_service": "svc",
    "environment": "development",
    "severity": "low",
    "evidence": [],
}


def test_oversized_description_is_rejected(client):
    payload = dict(BASE_EVENT, description="x" * 5000)
    resp = client.post("/events", json=payload, headers=ACTOR)
    assert resp.status_code == 422


def test_oversized_evidence_list_is_rejected(client):
    payload = dict(BASE_EVENT, evidence=[f"item-{i}" for i in range(25)])
    resp = client.post("/events", json=payload, headers=ACTOR)
    assert resp.status_code == 422


def test_oversized_source_field_is_rejected(client):
    payload = dict(BASE_EVENT, source="s" * 1000)
    resp = client.post("/events", json=payload, headers=ACTOR)
    assert resp.status_code == 422


def test_sql_injection_shaped_description_is_stored_literally_not_executed(client):
    malicious = "'; DROP TABLE operational_events; --"
    payload = dict(BASE_EVENT, description=malicious)
    resp = client.post("/events", json=payload, headers=ACTOR)
    assert resp.status_code == 201
    assert resp.json()["description"] == malicious

    # Table must still exist and be queryable — proves parameterized queries
    # (SQLAlchemy) prevented the injected statement from ever executing.
    list_resp = client.get("/events")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1


def test_script_tag_in_description_is_stored_as_plain_text(client):
    payload = dict(BASE_EVENT, description="<script>alert('xss')</script>")
    resp = client.post("/events", json=payload, headers=ACTOR)
    assert resp.status_code == 201
    # Stored verbatim as data; the dashboard's Jinja2 autoescaping (default
    # "on" for .html templates) is responsible for safe rendering, not the API.
    assert resp.json()["description"] == "<script>alert('xss')</script>"


def test_malformed_actor_header_is_rejected(client):
    resp = client.post("/events", json=BASE_EVENT, headers={"X-ArchGuard-Actor": "'; DROP TABLE users; --"})
    assert resp.status_code == 403


def test_empty_json_body_is_rejected(client):
    resp = client.post("/events", headers=ACTOR)
    assert resp.status_code == 422


def test_wrong_type_for_field_is_rejected(client):
    payload = dict(BASE_EVENT, evidence="not-a-list")
    resp = client.post("/events", json=payload, headers=ACTOR)
    assert resp.status_code == 422
