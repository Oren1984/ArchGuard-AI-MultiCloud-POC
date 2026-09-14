"""Gate 2: groundedness / source-data alignment.

Every cited evidence reference must correspond to something actually
present in the event's evidence list or description — otherwise the
recommendation is treated as ungrounded and blocked.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import CheckResult


@dataclass(frozen=True, slots=True)
class GroundingOutcome:
    result: CheckResult
    notes: str


def evaluate_grounding(
    evidence_references: list[str], event_evidence: list[str], event_description: str
) -> GroundingOutcome:
    if not evidence_references:
        return GroundingOutcome(CheckResult.WARNING, "No evidence references were cited.")

    haystack = " ".join(event_evidence).lower() + " " + event_description.lower()
    unmatched = [
        ref
        for ref in evidence_references
        if ref.split(":")[-1].strip().lower() not in haystack
        and ref.strip().lower() not in haystack
        and not ref.lower().startswith("event-description:")
    ]

    if unmatched:
        return GroundingOutcome(
            CheckResult.FAILED,
            f"{len(unmatched)} of {len(evidence_references)} evidence reference(s) do not "
            f"match any known event evidence or description content: {unmatched}.",
        )
    return GroundingOutcome(CheckResult.PASSED, "All evidence references are grounded in event data.")
