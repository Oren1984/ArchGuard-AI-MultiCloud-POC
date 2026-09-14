from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration

ACTOR = {"X-ArchGuard-Actor": "operator:test"}

VALID_EVENT = {
    "event_type": "performance_degradation",
    "source": "datadog",
    "description": "Latency briefly exceeded threshold.",
    "affected_service": "reporting-worker",
    "environment": "development",
    "severity": "low",
    "evidence": ["p99 latency 800ms"],
}


def test_create_event_returns_201_with_open_status(client):
    resp = client.post("/events", json=VALID_EVENT, headers=ACTOR)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "open"
    assert body["event_type"] == "performance_degradation"
    assert uuid.UUID(body["id"])


def test_create_event_without_actor_header_is_rejected(client):
    resp = client.post("/events", json=VALID_EVENT)
    assert resp.status_code == 403


def test_get_event_returns_created_event(client):
    created = client.post("/events", json=VALID_EVENT, headers=ACTOR).json()
    resp = client.get(f"/events/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_unknown_event_returns_404(client):
    resp = client.get(f"/events/{uuid.uuid4()}")
    assert resp.status_code == 404
    body = resp.json()
    assert "correlation_id" in body


def test_list_events_includes_created_event(client):
    created = client.post("/events", json=VALID_EVENT, headers=ACTOR).json()
    resp = client.get("/events")
    assert resp.status_code == 200
    ids = [e["id"] for e in resp.json()]
    assert created["id"] in ids


def test_list_events_filters_by_status(client):
    client.post("/events", json=VALID_EVENT, headers=ACTOR)
    resp = client.get("/events", params={"status": "blocked"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_event_rejects_invalid_enum_value(client):
    payload = dict(VALID_EVENT, environment="the_moon")
    resp = client.post("/events", json=payload, headers=ACTOR)
    assert resp.status_code == 422


def test_create_event_rejects_missing_required_field(client):
    payload = dict(VALID_EVENT)
    del payload["description"]
    resp = client.post("/events", json=payload, headers=ACTOR)
    assert resp.status_code == 422


def test_create_event_rejects_unknown_field(client):
    payload = dict(VALID_EVENT, unexpected="nope")
    resp = client.post("/events", json=payload, headers=ACTOR)
    assert resp.status_code == 422
