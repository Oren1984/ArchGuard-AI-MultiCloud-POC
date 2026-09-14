"""Gate 3: confidence threshold check.

Below the hard floor the recommendation is rejected outright (too
unreliable to route to anyone). Between the floor and the configured
threshold it passes but is flagged for mandatory human review.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import CheckResult

HARD_FLOOR = 0.20


@dataclass(frozen=True, slots=True)
class ConfidenceOutcome:
    result: CheckResult
    notes: str


def evaluate_confidence(confidence: float, threshold: float) -> ConfidenceOutcome:
    if confidence < HARD_FLOOR:
        return ConfidenceOutcome(
            CheckResult.FAILED, f"Confidence {confidence:.2f} is below the hard floor {HARD_FLOOR:.2f}."
        )
    if confidence < threshold:
        return ConfidenceOutcome(
            CheckResult.WARNING,
            f"Confidence {confidence:.2f} is below the review threshold {threshold:.2f}; human review required.",
        )
    return ConfidenceOutcome(
        CheckResult.PASSED, f"Confidence {confidence:.2f} meets the threshold {threshold:.2f}."
    )
