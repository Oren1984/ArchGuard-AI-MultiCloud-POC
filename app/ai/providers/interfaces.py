"""AI provider abstraction — the model/vendor-replacement boundary.

Providers return an *untrusted* raw dict. Nothing downstream trusts this
shape until app/ai/evaluation/schema_validator.py has validated it — that is
the whole point of the evaluation gate (spec §6.4, §8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class RecommendationRequest:
    event_id: str
    event_type: str
    environment: str
    severity: str
    affected_service: str
    description: str
    evidence: tuple[str, ...]
    risk_score: int
    risk_level: str
    prompt_version: str


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    raw_output: dict[str, Any]
    model_name: str
    model_version: str | None


class AIProvider(Protocol):
    """Implementations must raise ProviderUnavailableError on failure/timeout
    rather than returning a malformed or partial payload."""

    name: str

    def generate_recommendation(self, request: RecommendationRequest) -> ProviderResponse: ...
