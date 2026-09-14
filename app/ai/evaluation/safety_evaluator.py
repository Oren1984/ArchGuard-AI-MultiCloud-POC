"""Gate 4: dangerous/prohibited action detection.

Categorically dangerous actions are always blocked, regardless of
confidence or the deterministic risk level. No AI recommendation may
directly execute a real operational action (spec §6.5) — this check is
what enforces that at the evaluation layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import DANGEROUS_ACTIONS, CheckResult, ProposedActionType


@dataclass(frozen=True, slots=True)
class SafetyOutcome:
    result: CheckResult
    notes: str


def evaluate_safety(proposed_action: str) -> SafetyOutcome:
    try:
        action = ProposedActionType(proposed_action)
    except ValueError:
        return SafetyOutcome(CheckResult.FAILED, f"Unknown proposed action '{proposed_action}'.")

    if action in DANGEROUS_ACTIONS:
        return SafetyOutcome(
            CheckResult.FAILED,
            f"Proposed action '{action.value}' is categorically dangerous and is always blocked.",
        )
    return SafetyOutcome(
        CheckResult.PASSED, f"Proposed action '{action.value}' is not on the dangerous-action list."
    )
