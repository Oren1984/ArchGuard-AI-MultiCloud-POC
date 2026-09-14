"""End-to-end scenario (spec §14): create -> risk -> AI recommendation ->
evaluate -> route -> human approval -> audit -> final state via the API.
Also exercises the same workflow with the kill switch active and confirms
it fails closed.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

OPERATOR = {"X-ArchGuard-Actor": "operator:oncall"}
APPROVER = {"X-ArchGuard-Actor": "approver:sre-lead"}
ADMIN = {"X-ArchGuard-Actor": "admin:incident-commander"}

INCIDENT = {
    "event_type": "availability_outage",
    "source": "pagerduty",
    "description": "Elevated 5xx error rate on the payments service following the latest deploy.",
    "affected_service": "payments",
    "environment": "production",
    "severity": "high",
    "evidence": ["error rate 12% over 5 minutes", "deploy correlation confirmed"],
}


def test_full_workflow_end_to_end_with_human_approval(client):
    # 1. Establish provider eligibility (required before any AI run).
    eligibility = client.post("/providers/regression-evaluation", json={}, headers=OPERATOR)
    assert eligibility.status_code == 201
    assert eligibility.json()["eligible"] is True

    # 2. Create an operational event.
    create_resp = client.post("/events", json=INCIDENT, headers=OPERATOR)
    assert create_resp.status_code == 201
    event = create_resp.json()
    assert event["status"] == "open"

    # 3. Calculate deterministic risk.
    risk_resp = client.post(f"/events/{event['id']}/risk-assessment", headers=OPERATOR)
    assert risk_resp.status_code == 201
    risk = risk_resp.json()
    assert risk["level"] in ("high", "critical")
    assert len(risk["triggered_rules"]) > 0
    assert risk["explanation"]

    # 4. Request the mock AI recommendation (this also runs the evaluation gates).
    rec_resp = client.post(f"/events/{event['id']}/recommendations", headers=OPERATOR)
    assert rec_resp.status_code == 201
    recommendation = rec_resp.json()
    assert recommendation["provider"] == "mock"
    assert recommendation["confidence"] >= 0.0

    # 5. Evaluation result is retrievable and routes to human approval.
    evaluation = client.get(f"/recommendations/{recommendation['id']}/evaluation").json()
    assert evaluation["schema_valid"] is True
    assert evaluation["overall_result"] in ("passed", "warning")
    assert evaluation["requires_approval"] is True

    event_after_eval = client.get(f"/events/{event['id']}").json()
    assert event_after_eval["status"] == "pending_approval"
    assert recommendation["status"] == "pending_approval"

    # 6/7. Human approval.
    approval_resp = client.post(
        f"/recommendations/{recommendation['id']}/approval",
        json={"decision": "approved", "reason": "Matches the incident runbook."},
        headers=APPROVER,
    )
    assert approval_resp.status_code == 201
    approval = approval_resp.json()
    assert approval["decision"] == "approved"
    assert approval["approver_identity"] == "approver:sre-lead"

    # 8. All transitions recorded in the audit trail, hash chain intact.
    audit = client.get(f"/events/{event['id']}/audit").json()
    actions = [a["action"] for a in audit]
    for expected_action in (
        "event_created",
        "risk_assessed",
        "ai_recommendation_requested",
        "evaluation_completed",
        "approval_granted",
        "action_simulated",
    ):
        assert expected_action in actions

    verify = client.get("/audit/verify").json()
    assert verify["chain_intact"] is True

    # 9. Final state visible via the API (dashboard renders the same data).
    final_event = client.get(f"/events/{event['id']}").json()
    assert final_event["status"] == "action_simulated"
    final_recommendation = client.get(f"/recommendations/{recommendation['id']}").json()
    assert final_recommendation["final_status"] == "approved"

    dashboard_resp = client.get(f"/dashboard/events/{event['id']}")
    assert dashboard_resp.status_code == 200
    assert "action_simulated" in dashboard_resp.text


def test_full_workflow_fails_closed_when_kill_switch_active(client):
    client.post("/providers/regression-evaluation", json={}, headers=OPERATOR)

    activate = client.post("/governance/kill-switch/activate", json={"reason": "e2e drill"}, headers=ADMIN)
    assert activate.status_code == 201
    assert activate.json()["state"] == "active"

    try:
        event = client.post("/events", json=INCIDENT, headers=OPERATOR).json()
        assert event["status"] == "open"

        risk_resp = client.post(f"/events/{event['id']}/risk-assessment", headers=OPERATOR)
        assert risk_resp.status_code == 201  # deterministic risk engine is unaffected by the kill switch

        rec_resp = client.post(f"/events/{event['id']}/recommendations", headers=OPERATOR)
        assert rec_resp.status_code == 423  # AI processing blocked fail-closed

        final_event = client.get(f"/events/{event['id']}").json()
        assert final_event["status"] == "blocked"

        audit = client.get(f"/events/{event['id']}/audit").json()
        actions = [a["action"] for a in audit]
        assert "ai_recommendation_blocked_kill_switch" in actions
    finally:
        deactivate = client.post(
            "/governance/kill-switch/deactivate", json={"reason": "drill complete"}, headers=ADMIN
        )
        assert deactivate.status_code == 201
        assert deactivate.json()["state"] == "inactive"
