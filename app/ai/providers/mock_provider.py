"""Deterministic local mock AI provider. Requires no external credentials
and is the default provider (spec §6.4) so the whole workflow runs offline.

Determinism: output is a pure function of the request (hash-seeded), which
lets the consistency evaluator meaningfully assert "same input -> same
output" without needing a real, non-deterministic LLM.

Test-trigger keywords: including one of these substrings in the event
description deterministically exercises an AI-assurance failure path,
without needing a mocking framework in tests:
  TRIGGER_MALFORMED      -> schema-invalid payload (missing required field)
  TRIGGER_UNAVAILABLE    -> raises ProviderUnavailableError
  TRIGGER_UNGROUNDED     -> evidence_references cite non-existent evidence
  TRIGGER_LOW_CONFIDENCE -> confidence below the hard floor (evaluation FAILS)
  TRIGGER_BORDERLINE_CONFIDENCE -> confidence below the review threshold but
                                    above the hard floor (evaluation WARNS,
                                    routes to mandatory human review)
  TRIGGER_DANGEROUS      -> proposed_action is a categorically dangerous action
"""

from __future__ import annotations

import hashlib

from app.ai.providers.interfaces import ProviderResponse, RecommendationRequest
from app.domain.enums import RiskLevel
from app.domain.exceptions import ProviderUnavailableError

_RISK_PROFILE: dict[str, dict] = {
    RiskLevel.LOW.value: {
        "action": "notify_only",
        "confidence": 0.90,
        "requires_approval": False,
        "response": "Monitor the affected component and notify the on-call channel; no intervention required.",
    },
    RiskLevel.MEDIUM.value: {
        "action": "restart_service",
        "confidence": 0.78,
        "requires_approval": False,
        "response": "Restart the affected service instance and confirm health checks recover within 5 minutes.",
    },
    RiskLevel.HIGH.value: {
        "action": "rollback_deployment",
        "confidence": 0.68,
        "requires_approval": True,
        "response": "Roll back the most recent deployment for the affected service and validate against the previous known-good version.",
    },
    RiskLevel.CRITICAL.value: {
        "action": "escalate_to_human",
        "confidence": 0.55,
        "requires_approval": True,
        "response": "Escalate immediately to the incident commander; do not attempt automated remediation given the blast radius.",
    },
}


def _stable_unit_float(seed: str) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


class MockAIProvider:
    name = "mock"

    def generate_recommendation(self, request: RecommendationRequest) -> ProviderResponse:
        description = request.description

        if "TRIGGER_UNAVAILABLE" in description:
            raise ProviderUnavailableError(self.name, "Simulated provider outage for testing.")

        profile = _RISK_PROFILE.get(request.risk_level, _RISK_PROFILE[RiskLevel.MEDIUM.value])
        seed = f"{request.event_id}:{request.risk_level}:{request.prompt_version}"
        jitter = (_stable_unit_float(seed) - 0.5) * 0.06  # deterministic +/-3% jitter

        confidence = round(min(max(profile["confidence"] + jitter, 0.0), 1.0), 3)
        proposed_action = profile["action"]
        evidence_refs = (
            list(request.evidence[:3]) if request.evidence else [f"event-description:{request.event_id}"]
        )

        if "TRIGGER_LOW_CONFIDENCE" in description:
            confidence = 0.15

        if "TRIGGER_BORDERLINE_CONFIDENCE" in description:
            confidence = 0.35

        if "TRIGGER_DANGEROUS" in description:
            proposed_action = "delete_resource"

        if "TRIGGER_UNGROUNDED" in description:
            evidence_refs = ["nonexistent-evidence-ref-999"]

        raw_output: dict = {
            "summary": f"{request.event_type} detected on {request.affected_service} "
            f"in {request.environment} (risk: {request.risk_level}).",
            "suggested_response": profile["response"],
            "evidence_references": evidence_refs,
            "confidence": confidence,
            "proposed_action": proposed_action,
            "risk_notes": f"Deterministic mock assessment derived from risk level {request.risk_level}.",
            "requires_human_approval": profile["requires_approval"]
            or request.risk_level
            in (
                RiskLevel.HIGH.value,
                RiskLevel.CRITICAL.value,
            ),
        }

        if "TRIGGER_MALFORMED" in description:
            del raw_output["confidence"]  # violates the strict output schema

        return ProviderResponse(raw_output=raw_output, model_name="archguard-mock-v1", model_version="1.0.0")
