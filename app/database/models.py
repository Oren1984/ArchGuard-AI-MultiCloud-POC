"""SQLAlchemy ORM models — the PostgreSQL persistence schema.

Only this module and app/repositories/* know about SQLAlchemy. Services and
domain logic never import from here directly except through repositories.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.domain.enums import (
    AIProviderName,
    ApprovalDecisionType,
    CheckResult,
    Environment,
    EventStatus,
    EventType,
    KillSwitchState,
    ProposedActionType,
    RecommendationFinalStatus,
    RecommendationStatus,
    RiskLevel,
    SeverityIndicator,
)


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class OperationalEvent(Base):
    __tablename__ = "operational_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    event_type: Mapped[EventType] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_service: Mapped[str] = mapped_column(String(128), nullable=False)
    environment: Mapped[Environment] = mapped_column(String(32), nullable=False)
    severity: Mapped[SeverityIndicator] = mapped_column(String(32), nullable=False)
    status: Mapped[EventStatus] = mapped_column(String(32), nullable=False, default=EventStatus.OPEN.value)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    risk_assessments: Mapped[list[RiskAssessment]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list[AIRecommendation]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="event", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_operational_events_status", "status"),
        Index("ix_operational_events_environment", "environment"),
        Index("ix_operational_events_created_at", "created_at"),
    )


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("operational_events.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[RiskLevel] = mapped_column(String(16), nullable=False)
    triggered_rules: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped[OperationalEvent] = relationship(back_populates="risk_assessments")

    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_risk_assessments_score_range"),
        Index("ix_risk_assessments_event_id", "event_id"),
    )


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("operational_events.id", ondelete="CASCADE"), nullable=False
    )
    risk_assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("risk_assessments.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[AIProviderName] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    input_reference: Mapped[dict] = mapped_column(JSONB, nullable=False)

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_response: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_references: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    proposed_action: Mapped[ProposedActionType] = mapped_column(String(48), nullable=False)
    risk_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    raw_output: Mapped[dict] = mapped_column(JSONB, nullable=False)

    status: Mapped[RecommendationStatus] = mapped_column(
        String(32), nullable=False, default=RecommendationStatus.PENDING_EVALUATION.value
    )
    final_status: Mapped[RecommendationFinalStatus] = mapped_column(
        String(16), nullable=False, default=RecommendationFinalStatus.PENDING.value
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped[OperationalEvent] = relationship(back_populates="recommendations")
    risk_assessment: Mapped[RiskAssessment] = relationship()
    evaluation_result: Mapped[EvaluationResult | None] = relationship(
        back_populates="recommendation", uselist=False, cascade="all, delete-orphan"
    )
    approval_decision: Mapped[ApprovalDecision | None] = relationship(
        back_populates="recommendation", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0", name="ck_ai_recommendations_confidence_range"
        ),
        Index("ix_ai_recommendations_event_id", "event_id"),
        Index("ix_ai_recommendations_status", "status"),
    )


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[uuid.UUID] = _uuid_pk()
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_recommendations.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    schema_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    grounding_result: Mapped[CheckResult] = mapped_column(String(16), nullable=False)
    grounding_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence_result: Mapped[CheckResult] = mapped_column(String(16), nullable=False)
    confidence_value: Mapped[float] = mapped_column(Float, nullable=False)
    safety_result: Mapped[CheckResult] = mapped_column(String(16), nullable=False)
    safety_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    consistency_result: Mapped[CheckResult] = mapped_column(String(16), nullable=False)
    consistency_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    overall_result: Mapped[CheckResult] = mapped_column(String(16), nullable=False)
    risk_classification: Mapped[RiskLevel] = mapped_column(String(16), nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evaluation_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    recommendation: Mapped[AIRecommendation] = relationship(back_populates="evaluation_result")

    __table_args__ = (Index("ix_evaluation_results_recommendation_id", "recommendation_id"),)


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_recommendations.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("operational_events.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[ApprovalDecisionType] = mapped_column(String(16), nullable=False)
    approver_identity: Mapped[str] = mapped_column(String(128), nullable=False)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    recommendation: Mapped[AIRecommendation] = relationship(back_populates="approval_decision")

    __table_args__ = (Index("ix_approval_decisions_event_id", "event_id"),)


class AuditLog(Base):
    """Append-only, hash-chained audit trail.

    record_hash = sha256(previous_hash + canonical(action, details, actor, created_at)).
    This gives *tamper-evidence* (any edit breaks the chain when re-verified),
    not cryptographic immutability — see docs/SECURITY.md for the honest
    limitation statement (no external anchoring / no WORM storage in this POC).
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    # Monotonic ordering column, independent of UUID randomness and clock skew,
    # used as the authoritative order for hash-chain verification.
    seq: Mapped[int] = mapped_column(Integer, Identity(always=True), unique=True, nullable=False)
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("operational_events.id", ondelete="CASCADE"), nullable=True
    )
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped[OperationalEvent | None] = relationship(back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_event_id", "event_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )


class KillSwitchEvent(Base):
    __tablename__ = "kill_switch_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    state: Mapped[KillSwitchState] = mapped_column(String(16), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_kill_switch_events_created_at", "created_at"),)


class ProviderEligibilityRecord(Base):
    """Regression-evaluation record required before a provider/model config
    is eligible for use (spec §8, "Provider or model change")."""

    __tablename__ = "provider_eligibility_records"

    id: Mapped[uuid.UUID] = _uuid_pk()
    provider: Mapped[AIProviderName] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(32), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    pass_rate: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_provider_eligibility_provider_model", "provider", "model_name", "prompt_version"),
    )
