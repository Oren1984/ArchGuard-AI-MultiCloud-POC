"""Gate 1: output schema validation. A malformed or incomplete AI response
must not silently progress (spec §6.4, §8)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.ai.providers.schemas import AIRecommendationOutputSchema


@dataclass(frozen=True, slots=True)
class SchemaValidationOutcome:
    valid: bool
    parsed: AIRecommendationOutputSchema | None
    error: str | None


def validate_schema(raw_output: dict[str, Any]) -> SchemaValidationOutcome:
    try:
        parsed = AIRecommendationOutputSchema.model_validate(raw_output)
        return SchemaValidationOutcome(valid=True, parsed=parsed, error=None)
    except ValidationError as exc:
        return SchemaValidationOutcome(valid=False, parsed=None, error=str(exc))
