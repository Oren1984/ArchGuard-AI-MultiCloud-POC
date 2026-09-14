"""Strict schema the raw provider output must satisfy to progress past the
schema-validation evaluation gate. See app/ai/evaluation/schema_validator.py.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AIRecommendationOutputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=2000)
    suggested_response: str = Field(min_length=1, max_length=4000)
    evidence_references: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    proposed_action: str
    risk_notes: str = Field(default="", max_length=2000)
    requires_human_approval: bool
