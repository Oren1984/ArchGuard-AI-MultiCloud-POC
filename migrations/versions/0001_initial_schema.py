"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-14

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("affected_service", sa.String(128), nullable=False),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_operational_events_status", "operational_events", ["status"])
    op.create_index("ix_operational_events_environment", "operational_events", ["environment"])
    op.create_index("ix_operational_events_created_at", "operational_events", ["created_at"])

    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "event_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("operational_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column(
            "triggered_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"
        ),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("engine_version", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_risk_assessments_score_range"),
    )
    op.create_index("ix_risk_assessments_event_id", "risk_assessments", ["event_id"])

    op.create_table(
        "ai_recommendations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "event_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("operational_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "risk_assessment_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("risk_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("input_reference", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("suggested_response", sa.Text(), nullable=False),
        sa.Column(
            "evidence_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("proposed_action", sa.String(48), nullable=False),
        sa.Column("risk_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("requires_human_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("raw_output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending_evaluation"),
        sa.Column("final_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0", name="ck_ai_recommendations_confidence_range"
        ),
    )
    op.create_index("ix_ai_recommendations_event_id", "ai_recommendations", ["event_id"])
    op.create_index("ix_ai_recommendations_status", "ai_recommendations", ["status"])

    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "recommendation_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("ai_recommendations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("schema_valid", sa.Boolean(), nullable=False),
        sa.Column("grounding_result", sa.String(16), nullable=False),
        sa.Column("grounding_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("confidence_result", sa.String(16), nullable=False),
        sa.Column("confidence_value", sa.Float(), nullable=False),
        sa.Column("safety_result", sa.String(16), nullable=False),
        sa.Column("safety_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("consistency_result", sa.String(16), nullable=False),
        sa.Column("consistency_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("overall_result", sa.String(16), nullable=False),
        sa.Column("risk_classification", sa.String(16), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("evaluation_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evaluation_results_recommendation_id", "evaluation_results", ["recommendation_id"])

    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "recommendation_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("ai_recommendations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "event_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("operational_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("approver_identity", sa.String(128), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_approval_decisions_event_id", "approval_decisions", ["event_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("seq", sa.Integer(), sa.Identity(always=True), nullable=False, unique=True),
        sa.Column(
            "event_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("operational_events.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("previous_hash", sa.String(64), nullable=True),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_event_id", "audit_logs", ["event_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.create_table(
        "kill_switch_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_kill_switch_events_created_at", "kill_switch_events", ["created_at"])

    op.create_table(
        "provider_eligibility_records",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("dataset_version", sa.String(32), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("pass_rate", sa.Float(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_provider_eligibility_provider_model",
        "provider_eligibility_records",
        ["provider", "model_name", "prompt_version"],
    )


def downgrade() -> None:
    op.drop_table("provider_eligibility_records")
    op.drop_table("kill_switch_events")
    op.drop_table("audit_logs")
    op.drop_table("approval_decisions")
    op.drop_table("evaluation_results")
    op.drop_table("ai_recommendations")
    op.drop_table("risk_assessments")
    op.drop_table("operational_events")
