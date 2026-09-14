from __future__ import annotations

import pytest

from app.ai.providers.interfaces import RecommendationRequest
from app.ai.providers.mock_provider import MockAIProvider
from app.domain.exceptions import ProviderUnavailableError


def _request(
    description: str = "Normal incident description.", risk_level: str = "medium"
) -> RecommendationRequest:
    return RecommendationRequest(
        event_id="evt-1",
        event_type="deployment_failure",
        environment="staging",
        severity="medium",
        affected_service="checkout-api",
        description=description,
        evidence=("readiness probe failing",),
        risk_score=40,
        risk_level=risk_level,
        prompt_version="v1",
    )


def test_mock_provider_is_deterministic_for_identical_input():
    provider = MockAIProvider()
    r1 = provider.generate_recommendation(_request())
    r2 = provider.generate_recommendation(_request())
    assert r1.raw_output == r2.raw_output


def test_mock_provider_varies_with_risk_level():
    provider = MockAIProvider()
    low = provider.generate_recommendation(_request(risk_level="low"))
    critical = provider.generate_recommendation(_request(risk_level="critical"))
    assert low.raw_output["proposed_action"] != critical.raw_output["proposed_action"]
    assert low.raw_output["requires_human_approval"] is False
    assert critical.raw_output["requires_human_approval"] is True


def test_trigger_unavailable_raises():
    provider = MockAIProvider()
    with pytest.raises(ProviderUnavailableError):
        provider.generate_recommendation(_request(description="TRIGGER_UNAVAILABLE: outage"))


def test_trigger_malformed_omits_required_field():
    provider = MockAIProvider()
    response = provider.generate_recommendation(_request(description="TRIGGER_MALFORMED: bad output"))
    assert "confidence" not in response.raw_output


def test_trigger_low_confidence():
    provider = MockAIProvider()
    response = provider.generate_recommendation(_request(description="TRIGGER_LOW_CONFIDENCE: uncertain"))
    assert response.raw_output["confidence"] < 0.2


def test_trigger_borderline_confidence():
    provider = MockAIProvider()
    response = provider.generate_recommendation(_request(description="TRIGGER_BORDERLINE_CONFIDENCE: unsure"))
    assert response.raw_output["confidence"] == 0.35


def test_trigger_dangerous_action():
    provider = MockAIProvider()
    response = provider.generate_recommendation(_request(description="TRIGGER_DANGEROUS: risky"))
    assert response.raw_output["proposed_action"] == "delete_resource"


def test_trigger_ungrounded_evidence():
    provider = MockAIProvider()
    response = provider.generate_recommendation(_request(description="TRIGGER_UNGROUNDED: mismatch"))
    assert response.raw_output["evidence_references"] == ["nonexistent-evidence-ref-999"]


def test_confidence_within_valid_range():
    provider = MockAIProvider()
    for level in ("low", "medium", "high", "critical"):
        response = provider.generate_recommendation(_request(risk_level=level))
        assert 0.0 <= response.raw_output["confidence"] <= 1.0
