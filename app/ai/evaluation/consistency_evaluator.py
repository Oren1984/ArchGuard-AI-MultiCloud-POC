"""Gate 5: basic deterministic consistency check.

Re-invokes the provider for the same input and compares the proposed
action and confidence (within a small tolerance). A real LLM might drift
slightly between calls — that produces a WARNING (flag for review), not a
hard failure; only schema/safety/grounding/confidence-floor failures block
outright.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.evaluation.schema_validator import validate_schema
from app.ai.providers.interfaces import AIProvider, RecommendationRequest
from app.domain.enums import CheckResult
from app.domain.exceptions import ProviderUnavailableError

CONFIDENCE_TOLERANCE = 0.10


@dataclass(frozen=True, slots=True)
class ConsistencyOutcome:
    result: CheckResult
    notes: str


def evaluate_consistency(
    provider: AIProvider,
    request: RecommendationRequest,
    first_proposed_action: str,
    first_confidence: float,
    extra_runs: int,
) -> ConsistencyOutcome:
    if extra_runs <= 0:
        return ConsistencyOutcome(CheckResult.PASSED, "Consistency check skipped (0 extra runs configured).")

    mismatches = 0
    errors = 0
    for _ in range(extra_runs):
        try:
            response = provider.generate_recommendation(request)
        except ProviderUnavailableError:
            errors += 1
            continue
        outcome = validate_schema(response.raw_output)
        if not outcome.valid or outcome.parsed is None:
            mismatches += 1
            continue
        same_action = outcome.parsed.proposed_action == first_proposed_action
        same_confidence = abs(outcome.parsed.confidence - first_confidence) <= CONFIDENCE_TOLERANCE
        if not (same_action and same_confidence):
            mismatches += 1

    if errors == extra_runs:
        return ConsistencyOutcome(
            CheckResult.WARNING, "Could not verify consistency: provider was unavailable on repeat calls."
        )
    if mismatches:
        return ConsistencyOutcome(
            CheckResult.WARNING,
            f"{mismatches}/{extra_runs} repeat call(s) diverged in proposed action or confidence.",
        )
    return ConsistencyOutcome(
        CheckResult.PASSED, f"All {extra_runs} repeat call(s) matched the original output within tolerance."
    )
