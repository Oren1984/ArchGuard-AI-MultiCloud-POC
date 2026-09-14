from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

OPERATOR = {"X-ArchGuard-Actor": "operator:test"}
APPROVER = {"X-ArchGuard-Actor": "approver:jane"}
ADMIN = {"X-ArchGuard-Actor": "admin:oncall"}


def _create_event(client, **overrides) -> dict:
    payload = {
        "event_type": "availability_outage",
        "source": "pagerduty",
        "description": "Elevated 5xx error rate on the payments service.",
        "affected_service": "payments",
        "environment": "production",
        "severity": "high",
        "evidence": ["error rate 12% over 5 minutes"],
    }
    payload.update(overrides)
    resp = client.post("/events", json=payload, headers=OPERATOR)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _ensure_eligibility(client) -> None:
    resp = client.post("/providers/regression-evaluation", json={}, headers=OPERATOR)
    assert resp.status_code == 201, resp.text
    assert resp.json()["eligible"] is True


def test_recommendation_blocked_when_no_eligibility_record(client):
    event = _create_event(client)
    client.post(f"/events/{event['id']}/risk-assessment", headers=OPERATOR)
    resp = client.post(f"/events/{event['id']}/recommendations", headers=OPERATOR)
    assert resp.status_code == 409
    assert resp.json()["error"] == "ProviderNotEligibleError"


def test_recommendation_before_risk_assessment_is_invalid_transition(client):
    _ensure_eligibility(client)
    event = _create_event(client)
    resp = client.post(f"/events/{event['id']}/recommendations", headers=OPERATOR)
    assert resp.status_code == 409


def test_high_risk_flow_requires_approval_then_simulates_action(client):
    _ensure_eligibility(client)
    event = _create_event(client)  # production + high severity + critical service -> HIGH/CRITICAL risk

    risk_resp = client.post(f"/events/{event['id']}/risk-assessment", headers=OPERATOR)
    assert risk_resp.status_code == 201
    assert risk_resp.json()["level"] in ("high", "critical")

    rec_resp = client.post(f"/events/{event['id']}/recommendations", headers=OPERATOR)
    assert rec_resp.status_code == 201
    recommendation = rec_resp.json()
    assert recommendation["status"] == "pending_approval"

    event_after = client.get(f"/events/{event['id']}").json()
    assert event_after["status"] == "pending_approval"

    eval_resp = client.get(f"/recommendations/{recommendation['id']}/evaluation")
    assert eval_resp.status_code == 200
    assert eval_resp.json()["requires_approval"] is True

    approval_resp = client.post(
        f"/recommendations/{recommendation['id']}/approval",
        json={"decision": "approved", "reason": "matches runbook"},
        headers=APPROVER,
    )
    assert approval_resp.status_code == 201
    assert approval_resp.json()["approver_identity"] == "approver:jane"

    final_event = client.get(f"/events/{event['id']}").json()
    assert final_event["status"] == "action_simulated"

    final_rec = client.get(f"/recommendations/{recommendation['id']}").json()
    assert final_rec["final_status"] == "approved"


def test_rejection_path(client):
    _ensure_eligibility(client)
    event = _create_event(
        client, event_type="unauthorized_access", severity="critical", affected_service="auth"
    )
    client.post(f"/events/{event['id']}/risk-assessment", headers=OPERATOR)
    rec = client.post(f"/events/{event['id']}/recommendations", headers=OPERATOR).json()

    resp = client.post(
        f"/recommendations/{rec['id']}/approval",
        json={"decision": "rejected", "reason": "manual escalation instead"},
        headers=APPROVER,
    )
    assert resp.status_code == 201
    assert resp.json()["decision"] == "rejected"

    event_after = client.get(f"/events/{event['id']}").json()
    assert event_after["status"] == "rejected"


def test_low_risk_auto_clears_without_approval(client):
    _ensure_eligibility(client)
    event = _create_event(
        client,
        event_type="performance_degradation",
        environment="development",
        severity="low",
        affected_service="reporting-worker",
        description="Minor latency blip, no user impact.",
    )
    client.post(f"/events/{event['id']}/risk-assessment", headers=OPERATOR)
    rec = client.post(f"/events/{event['id']}/recommendations", headers=OPERATOR).json()
    assert rec["final_status"] == "approved"

    event_after = client.get(f"/events/{event['id']}").json()
    assert event_after["status"] == "action_simulated"


def test_dangerous_action_is_blocked_by_safety_gate(client):
    _ensure_eligibility(client)
    event = _create_event(client, description="TRIGGER_DANGEROUS: corrupting records in the ledger.")
    client.post(f"/events/{event['id']}/risk-assessment", headers=OPERATOR)
    rec = client.post(f"/events/{event['id']}/recommendations", headers=OPERATOR).json()
    assert rec["status"] == "blocked"
    assert rec["final_status"] == "blocked"

    event_after = client.get(f"/events/{event['id']}").json()
    assert event_after["status"] == "blocked"


def test_approval_rejects_unauthorized_actor_role(client):
    _ensure_eligibility(client)
    event = _create_event(client)
    client.post(f"/events/{event['id']}/risk-assessment", headers=OPERATOR)
    rec = client.post(f"/events/{event['id']}/recommendations", headers=OPERATOR).json()

    resp = client.post(
        f"/recommendations/{rec['id']}/approval",
        json={"decision": "approved"},
        headers=OPERATOR,  # not an approver/admin
    )
    assert resp.status_code == 403


def test_approval_on_non_pending_recommendation_is_invalid_transition(client):
    _ensure_eligibility(client)
    event = _create_event(
        client,
        event_type="performance_degradation",
        environment="development",
        severity="low",
        description="ok",
    )
    client.post(f"/events/{event['id']}/risk-assessment", headers=OPERATOR)
    rec = client.post(f"/events/{event['id']}/recommendations", headers=OPERATOR).json()
    assert rec["final_status"] == "approved"  # already auto-cleared

    resp = client.post(
        f"/recommendations/{rec['id']}/approval", json={"decision": "approved"}, headers=APPROVER
    )
    assert resp.status_code == 409


def test_kill_switch_blocks_ai_recommendation_and_fails_closed(client):
    _ensure_eligibility(client)
    activate = client.post("/governance/kill-switch/activate", json={"reason": "drill"}, headers=ADMIN)
    assert activate.status_code == 201
    assert activate.json()["state"] == "active"

    try:
        event = _create_event(client)
        client.post(f"/events/{event['id']}/risk-assessment", headers=OPERATOR)
        resp = client.post(f"/events/{event['id']}/recommendations", headers=OPERATOR)
        assert resp.status_code == 423

        event_after = client.get(f"/events/{event['id']}").json()
        assert event_after["status"] == "blocked"
    finally:
        deactivate = client.post(
            "/governance/kill-switch/deactivate", json={"reason": "drill over"}, headers=ADMIN
        )
        assert deactivate.status_code == 201
        assert deactivate.json()["state"] == "inactive"


def test_kill_switch_toggle_requires_admin_role(client):
    resp = client.post("/governance/kill-switch/activate", json={}, headers=APPROVER)
    assert resp.status_code == 403


def test_audit_trail_covers_full_workflow(client):
    _ensure_eligibility(client)
    event = _create_event(client)
    client.post(f"/events/{event['id']}/risk-assessment", headers=OPERATOR)
    rec = client.post(f"/events/{event['id']}/recommendations", headers=OPERATOR).json()
    client.post(f"/recommendations/{rec['id']}/approval", json={"decision": "approved"}, headers=APPROVER)

    audit_resp = client.get(f"/events/{event['id']}/audit")
    assert audit_resp.status_code == 200
    actions = [entry["action"] for entry in audit_resp.json()]
    assert "event_created" in actions
    assert "risk_assessed" in actions
    assert "ai_recommendation_requested" in actions
    assert "evaluation_completed" in actions
    assert "approval_granted" in actions
    assert "action_simulated" in actions

    verify_resp = client.get("/audit/verify")
    assert verify_resp.status_code == 200
    assert verify_resp.json()["chain_intact"] is True
