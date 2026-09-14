"""No AI recommendation may directly execute a real operational action, and
categorically dangerous proposed actions must always be blocked — even at
low deterministic risk and even when the AI itself claims no approval is
needed (spec §6.5, §8)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

ACTOR = {"X-ArchGuard-Actor": "operator:test"}


def test_dangerous_action_blocked_even_at_low_deterministic_risk(client):
    client.post("/providers/regression-evaluation", json={}, headers=ACTOR)
    event = client.post(
        "/events",
        json={
            "event_type": "performance_degradation",
            "source": "synthetic-test",
            "description": "TRIGGER_DANGEROUS: minor issue but AI proposes a dangerous action.",
            "affected_service": "reporting-worker",
            "environment": "development",
            "severity": "low",
            "evidence": [],
        },
        headers=ACTOR,
    ).json()
    risk = client.post(f"/events/{event['id']}/risk-assessment", headers=ACTOR).json()
    assert risk["level"] == "low"  # low deterministic risk

    rec = client.post(f"/events/{event['id']}/recommendations", headers=ACTOR).json()
    assert rec["proposed_action"] == "delete_resource"
    assert rec["status"] == "blocked"
    assert rec["final_status"] == "blocked"

    evaluation = client.get(f"/recommendations/{rec['id']}/evaluation").json()
    assert evaluation["safety_result"] == "failed"
    assert evaluation["overall_result"] == "failed"

    event_after = client.get(f"/events/{event['id']}").json()
    assert event_after["status"] == "blocked"


def test_simulated_action_response_is_clearly_marked_as_simulated(client):
    client.post("/providers/regression-evaluation", json={}, headers=ACTOR)
    event = client.post(
        "/events",
        json={
            "event_type": "performance_degradation",
            "source": "synthetic-test",
            "description": "Minor latency blip.",
            "affected_service": "reporting-worker",
            "environment": "development",
            "severity": "low",
            "evidence": [],
        },
        headers=ACTOR,
    ).json()
    client.post(f"/events/{event['id']}/risk-assessment", headers=ACTOR)
    client.post(f"/events/{event['id']}/recommendations", headers=ACTOR)

    audit = client.get(f"/events/{event['id']}/audit").json()
    simulated_entries = [a for a in audit if a["action"] == "action_simulated"]
    assert len(simulated_entries) == 1
    assert simulated_entries[0]["details"]["simulated"] is True
    assert "[SIMULATED]" in simulated_entries[0]["details"]["message"]
