from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_health_always_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_reports_database_available(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["database_available"] is True


def test_metrics_endpoint_exposes_prometheus_format(client):
    client.post(
        "/events",
        json={
            "event_type": "performance_degradation",
            "source": "datadog",
            "description": "desc",
            "affected_service": "svc",
            "environment": "development",
            "severity": "low",
            "evidence": [],
        },
        headers={"X-ArchGuard-Actor": "operator:test"},
    )
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "archguard_events_created_total" in resp.text


def test_openapi_docs_available(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "ArchGuard AI MultiCloud POC"
