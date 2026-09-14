"""Unauthorized/invalid approval attempts within the POC's lightweight
identity model (spec §14 Security Tests)."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration

OPERATOR = {"X-ArchGuard-Actor": "operator:test"}
APPROVER = {"X-ArchGuard-Actor": "approver:jane"}
ADMIN = {"X-ArchGuard-Actor": "admin:oncall"}

HIGH_RISK_EVENT = {
    "event_type": "availability_outage",
    "source": "pagerduty",
    "description": "Elevated 5xx error rate on the payments service.",
    "affected_service": "payments",
    "environment": "production",
    "severity": "high",
    "evidence": ["error rate 12% over 5 minutes"],
}


def _pending_recommendation(client) -> dict:
    client.post("/providers/regression-evaluation", json={}, headers=OPERATOR)
    event = client.post("/events", json=HIGH_RISK_EVENT, headers=OPERATOR).json()
    client.post(f"/events/{event['id']}/risk-assessment", headers=OPERATOR)
    return client.post(f"/events/{event['id']}/recommendations", headers=OPERATOR).json()


def test_approval_without_actor_header_is_rejected(client):
    rec = _pending_recommendation(client)
    resp = client.post(f"/recommendations/{rec['id']}/approval", json={"decision": "approved"})
    assert resp.status_code == 403


def test_approval_from_operator_role_is_rejected(client):
    rec = _pending_recommendation(client)
    resp = client.post(
        f"/recommendations/{rec['id']}/approval", json={"decision": "approved"}, headers=OPERATOR
    )
    assert resp.status_code == 403


def test_approval_with_malformed_actor_identity_is_rejected(client):
    rec = _pending_recommendation(client)
    resp = client.post(
        f"/recommendations/{rec['id']}/approval",
        json={"decision": "approved"},
        headers={"X-ArchGuard-Actor": "approver:<script>"},
    )
    assert resp.status_code == 403


def test_approval_on_unknown_recommendation_returns_404(client):
    resp = client.post(
        f"/recommendations/{uuid.uuid4()}/approval", json={"decision": "approved"}, headers=APPROVER
    )
    assert resp.status_code == 404


def test_double_approval_second_attempt_is_invalid_transition(client):
    rec = _pending_recommendation(client)
    first = client.post(
        f"/recommendations/{rec['id']}/approval", json={"decision": "approved"}, headers=APPROVER
    )
    assert first.status_code == 201

    second = client.post(
        f"/recommendations/{rec['id']}/approval", json={"decision": "approved"}, headers=APPROVER
    )
    assert second.status_code == 409


def test_admin_role_is_also_permitted_to_approve(client):
    rec = _pending_recommendation(client)
    resp = client.post(f"/recommendations/{rec['id']}/approval", json={"decision": "approved"}, headers=ADMIN)
    assert resp.status_code == 201
