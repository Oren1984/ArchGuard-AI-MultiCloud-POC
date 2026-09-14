"""AI Assurance tests (spec §14): every documented failure path must be
recorded and must not silently progress through the workflow."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

ACTOR = {"X-ArchGuard-Actor": "operator:test"}
LOW_RISK_BASE = {
    "event_type": "performance_degradation",
    "source": "synthetic-test",
    "affected_service": "reporting-worker",
    "environment": "development",
    "severity": "low",
    "evidence": ["synthetic evidence item"],
}


def _run(client, description: str) -> tuple[dict, dict]:
    client.post("/providers/regression-evaluation", json={}, headers=ACTOR)
    event = client.post("/events", json=dict(LOW_RISK_BASE, description=description), headers=ACTOR).json()
    client.post(f"/events/{event['id']}/risk-assessment", headers=ACTOR)
    return event, client.post(f"/events/{event['id']}/recommendations", headers=ACTOR)


def test_valid_mock_response_evaluates_and_auto_clears(client):
    event, resp = _run(client, "Normal, unremarkable operational event.")
    assert resp.status_code == 201
    rec = resp.json()
    assert rec["status"] == "evaluated" or rec["status"] == "approved"
    evaluation = client.get(f"/recommendations/{rec['id']}/evaluation").json()
    assert evaluation["schema_valid"] is True
    assert evaluation["overall_result"] in ("passed", "warning")


def test_malformed_model_response_is_blocked_not_silently_progressed(client):
    event, resp = _run(client, "TRIGGER_MALFORMED: incomplete output from provider.")
    assert resp.status_code == 201
    rec = resp.json()
    assert rec["status"] == "blocked"
    assert rec["final_status"] == "blocked"
    evaluation = client.get(f"/recommendations/{rec['id']}/evaluation").json()
    assert evaluation["schema_valid"] is False
    assert evaluation["overall_result"] == "failed"


def test_provider_unavailable_is_recorded_and_blocks(client):
    event, resp = _run(client, "TRIGGER_UNAVAILABLE: provider outage simulated.")
    assert resp.status_code == 502
    rec = client.get(f"/events/{event['id']}/recommendations/latest").json()
    assert rec["status"] == "error"
    assert rec["final_status"] == "blocked"
    event_after = client.get(f"/events/{event['id']}").json()
    assert event_after["status"] == "blocked"


def test_ungrounded_recommendation_is_blocked(client):
    event, resp = _run(client, "TRIGGER_UNGROUNDED: evidence references will not match.")
    rec = resp.json()
    evaluation = client.get(f"/recommendations/{rec['id']}/evaluation").json()
    assert evaluation["grounding_result"] == "failed"
    assert evaluation["overall_result"] == "failed"
    assert rec["status"] == "blocked"


def test_low_confidence_below_hard_floor_is_blocked(client):
    event, resp = _run(client, "TRIGGER_LOW_CONFIDENCE: highly uncertain output.")
    rec = resp.json()
    evaluation = client.get(f"/recommendations/{rec['id']}/evaluation").json()
    assert evaluation["confidence_result"] == "failed"
    assert rec["status"] == "blocked"


def test_borderline_confidence_requires_human_review_not_hard_block(client):
    event, resp = _run(client, "TRIGGER_BORDERLINE_CONFIDENCE: somewhat uncertain output.")
    rec = resp.json()
    assert rec["status"] == "pending_approval"
    evaluation = client.get(f"/recommendations/{rec['id']}/evaluation").json()
    assert evaluation["confidence_result"] == "warning"
    assert evaluation["requires_approval"] is True

    event_after = client.get(f"/events/{event['id']}").json()
    assert event_after["status"] == "pending_approval"


def test_regression_evaluation_required_before_new_provider_config_eligible(client):
    # No regression-evaluation run yet for this fresh transaction/provider config.
    event = client.post("/events", json=dict(LOW_RISK_BASE, description="ok"), headers=ACTOR).json()
    client.post(f"/events/{event['id']}/risk-assessment", headers=ACTOR)
    resp = client.post(f"/events/{event['id']}/recommendations", headers=ACTOR)
    assert resp.status_code == 409
    assert resp.json()["error"] == "ProviderNotEligibleError"

    # After running the regression evaluation, the same provider/model config becomes eligible.
    reg = client.post("/providers/regression-evaluation", json={}, headers=ACTOR)
    assert reg.status_code == 201
    assert reg.json()["eligible"] is True

    resp2 = client.post(f"/events/{event['id']}/recommendations", headers=ACTOR)
    assert resp2.status_code == 201


def test_fallback_when_ai_unavailable_deterministic_risk_still_usable(client):
    """The deterministic risk engine must remain usable even when the AI
    provider is unavailable — it never depends on a live provider call."""
    event = client.post(
        "/events", json=dict(LOW_RISK_BASE, description="AI outage scenario"), headers=ACTOR
    ).json()
    risk_resp = client.post(f"/events/{event['id']}/risk-assessment", headers=ACTOR)
    assert risk_resp.status_code == 201
    assert risk_resp.json()["level"] == "low"
    # Risk assessment succeeded independent of any AI recommendation call.
