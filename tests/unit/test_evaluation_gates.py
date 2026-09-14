from __future__ import annotations

from app.ai.evaluation.confidence_evaluator import HARD_FLOOR, evaluate_confidence
from app.ai.evaluation.consistency_evaluator import evaluate_consistency
from app.ai.evaluation.grounding_evaluator import evaluate_grounding
from app.ai.evaluation.safety_evaluator import evaluate_safety
from app.ai.evaluation.schema_validator import validate_schema
from app.ai.providers.interfaces import ProviderResponse, RecommendationRequest
from app.domain.enums import CheckResult

VALID_OUTPUT = {
    "summary": "Summary",
    "suggested_response": "Do the thing.",
    "evidence_references": ["error rate 12%"],
    "confidence": 0.8,
    "proposed_action": "restart_service",
    "risk_notes": "notes",
    "requires_human_approval": False,
}


def test_schema_validation_accepts_well_formed_output():
    outcome = validate_schema(VALID_OUTPUT)
    assert outcome.valid is True
    assert outcome.parsed.confidence == 0.8


def test_schema_validation_rejects_missing_required_field():
    payload = dict(VALID_OUTPUT)
    del payload["confidence"]
    outcome = validate_schema(payload)
    assert outcome.valid is False
    assert outcome.parsed is None


def test_schema_validation_rejects_extra_fields():
    payload = dict(VALID_OUTPUT)
    payload["unexpected_field"] = "nope"
    outcome = validate_schema(payload)
    assert outcome.valid is False


def test_schema_validation_rejects_out_of_range_confidence():
    payload = dict(VALID_OUTPUT, confidence=1.5)
    outcome = validate_schema(payload)
    assert outcome.valid is False


def test_grounding_passes_when_reference_matches_event_evidence():
    outcome = evaluate_grounding(["error rate 12%"], ["error rate 12% over 5 minutes"], "desc")
    assert outcome.result == CheckResult.PASSED


def test_grounding_fails_when_reference_matches_nothing():
    outcome = evaluate_grounding(["nonexistent-evidence-ref-999"], ["error rate 12%"], "desc")
    assert outcome.result == CheckResult.FAILED


def test_grounding_warns_when_no_references_cited():
    outcome = evaluate_grounding([], ["error rate 12%"], "desc")
    assert outcome.result == CheckResult.WARNING


def test_confidence_passes_above_threshold():
    outcome = evaluate_confidence(0.9, threshold=0.55)
    assert outcome.result == CheckResult.PASSED


def test_confidence_warns_between_floor_and_threshold():
    outcome = evaluate_confidence(0.3, threshold=0.55)
    assert outcome.result == CheckResult.WARNING


def test_confidence_fails_below_hard_floor():
    outcome = evaluate_confidence(HARD_FLOOR - 0.01, threshold=0.55)
    assert outcome.result == CheckResult.FAILED


def test_safety_passes_for_normal_action():
    outcome = evaluate_safety("restart_service")
    assert outcome.result == CheckResult.PASSED


def test_safety_fails_for_dangerous_action():
    outcome = evaluate_safety("delete_resource")
    assert outcome.result == CheckResult.FAILED


def test_safety_fails_for_unknown_action():
    outcome = evaluate_safety("launch_the_missiles")
    assert outcome.result == CheckResult.FAILED


class _StableProvider:
    name = "test-stable"

    def generate_recommendation(self, request: RecommendationRequest) -> ProviderResponse:
        return ProviderResponse(raw_output=dict(VALID_OUTPUT), model_name="m", model_version="1")


class _DriftingProvider:
    name = "test-drifting"

    def __init__(self) -> None:
        self.calls = 0

    def generate_recommendation(self, request: RecommendationRequest) -> ProviderResponse:
        self.calls += 1
        payload = dict(VALID_OUTPUT, proposed_action="escalate_to_human", confidence=0.1)
        return ProviderResponse(raw_output=payload, model_name="m", model_version="1")


def _request() -> RecommendationRequest:
    return RecommendationRequest(
        event_id="e1",
        event_type="performance_degradation",
        environment="development",
        severity="low",
        affected_service="svc",
        description="desc",
        evidence=(),
        risk_score=10,
        risk_level="low",
        prompt_version="v1",
    )


def test_consistency_passes_when_repeat_calls_match():
    outcome = evaluate_consistency(_StableProvider(), _request(), "restart_service", 0.8, extra_runs=2)
    assert outcome.result == CheckResult.PASSED


def test_consistency_warns_when_repeat_calls_diverge():
    outcome = evaluate_consistency(_DriftingProvider(), _request(), "restart_service", 0.8, extra_runs=2)
    assert outcome.result == CheckResult.WARNING


def test_consistency_skipped_when_zero_extra_runs():
    outcome = evaluate_consistency(_StableProvider(), _request(), "restart_service", 0.8, extra_runs=0)
    assert outcome.result == CheckResult.PASSED
    assert "skipped" in outcome.notes.lower()
