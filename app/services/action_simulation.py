"""Simulated action execution.

No AI recommendation may directly execute a real operational action
(spec §6.5). This module never calls a cloud SDK or external system — it
returns a clearly-marked, audited simulation result only.
"""

from __future__ import annotations

from datetime import UTC, datetime


def simulate_action(proposed_action: str, event_id: str) -> dict:
    return {
        "simulated": True,
        "action": proposed_action,
        "target_event_id": event_id,
        "message": f"[SIMULATED] Would execute '{proposed_action}'. No real operational action was taken.",
        "simulated_at": datetime.now(UTC).isoformat(),
    }
