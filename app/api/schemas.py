"""Strict Pydantic request/response models for the API boundary.

All external input is validated here — length bounds, enum membership,
and list-size caps guard against oversized or malformed payloads (spec
§14 "Security Tests").
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    ApprovalDecisionType,
    Environment,
    EventType,
    KillSwitchState,
    SeverityIndicator,
)

MAX_TEXT = 4000
MAX_SHORT_TEXT = 256
MAX_EVIDENCE_ITEMS = 20


class EventCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: EventType
    source: str = Field(min_length=1, max_length=MAX_SHORT_TEXT)
    description: str = Field(min_length=1, max_length=MAX_TEXT)
    affected_service: str = Field(min_length=1, max_length=MAX_SHORT_TEXT)
    environment: Environment
    severity: SeverityIndicator
    evidence: list[str] = Field(default_factory=list, max_length=MAX_EVIDENCE_ITEMS)


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    source: str
    description: str
    affected_service: str
    environment: str
    severity: str
    status: str
    evidence: list[str]
    created_at: datetime
    updated_at: datetime


class TriggeredRuleModel(BaseModel):
    rule_id: str
    description: str
    points: int
    category: str


class RiskAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    score: int
    level: str
    triggered_rules: list[dict[str, Any]]
    explanation: str
    engine_version: str
    created_at: datetime


class AIRecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    risk_assessment_id: uuid.UUID
    provider: str
    model_name: str
    model_version: str | None
    prompt_version: str
    summary: str
    suggested_response: str
    evidence_references: list[str]
    confidence: float
    proposed_action: str
    risk_notes: str
    requires_human_approval: bool
    status: str
    final_status: str
    created_at: datetime


class EvaluationResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recommendation_id: uuid.UUID
    schema_valid: bool
    grounding_result: str
    grounding_notes: str
    confidence_result: str
    confidence_value: float
    safety_result: str
    safety_notes: str
    consistency_result: str
    consistency_notes: str
    overall_result: str
    risk_classification: str
    requires_approval: bool
    evaluation_summary: str
    created_at: datetime


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ApprovalDecisionType
    reason: str | None = Field(default=None, max_length=MAX_TEXT)


class ApprovalDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recommendation_id: uuid.UUID
    event_id: uuid.UUID
    decision: str
    approver_identity: str
    decision_reason: str | None
    decided_at: datetime


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seq: int
    event_id: uuid.UUID | None
    actor: str
    action: str
    details: dict[str, Any]
    previous_hash: str | None
    record_hash: str
    created_at: datetime


class KillSwitchToggleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=MAX_TEXT)


class KillSwitchStateResponse(BaseModel):
    state: KillSwitchState
    actor: str | None = None
    reason: str | None = None
    changed_at: datetime | None = None


class ProviderEligibilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    model_name: str
    prompt_version: str
    dataset_version: str
    passed: bool
    pass_rate: float
    eligible: bool
    details: dict[str, Any]
    evaluated_at: datetime


class RegressionEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str | None = Field(default=None, max_length=MAX_SHORT_TEXT)
    prompt_version: str | None = Field(default=None, max_length=64)


class ErrorResponse(BaseModel):
    error: str
    detail: str
    correlation_id: str
