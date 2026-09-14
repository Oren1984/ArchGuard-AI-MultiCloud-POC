"""PostgreSQL/SQLAlchemy implementations of the repository Protocols."""

from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import models
from app.domain.enums import EventStatus


class SqlAlchemyEventRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, event: models.OperationalEvent) -> models.OperationalEvent:
        self._db.add(event)
        self._db.flush()
        return event

    def get(self, event_id: uuid.UUID) -> models.OperationalEvent | None:
        return self._db.get(models.OperationalEvent, event_id)

    def list(
        self,
        limit: int,
        offset: int,
        status: EventStatus | None = None,
        environment: str | None = None,
    ) -> list[models.OperationalEvent]:
        stmt = select(models.OperationalEvent).order_by(models.OperationalEvent.created_at.desc())
        if status is not None:
            stmt = stmt.where(models.OperationalEvent.status == status.value)
        if environment is not None:
            stmt = stmt.where(models.OperationalEvent.environment == environment)
        stmt = stmt.limit(limit).offset(offset)
        return list(self._db.scalars(stmt).all())

    def update_status(self, event_id: uuid.UUID, status: EventStatus) -> models.OperationalEvent:
        event = self._db.get(models.OperationalEvent, event_id)
        if event is None:
            raise ValueError(f"Event {event_id} not found")
        event.status = status.value
        self._db.flush()
        return event


class SqlAlchemyRiskAssessmentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, assessment: models.RiskAssessment) -> models.RiskAssessment:
        self._db.add(assessment)
        self._db.flush()
        return assessment

    def get_latest_for_event(self, event_id: uuid.UUID) -> models.RiskAssessment | None:
        stmt = (
            select(models.RiskAssessment)
            .where(models.RiskAssessment.event_id == event_id)
            .order_by(models.RiskAssessment.created_at.desc())
            .limit(1)
        )
        return self._db.scalars(stmt).first()


class SqlAlchemyRecommendationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, recommendation: models.AIRecommendation) -> models.AIRecommendation:
        self._db.add(recommendation)
        self._db.flush()
        return recommendation

    def get(self, recommendation_id: uuid.UUID) -> models.AIRecommendation | None:
        return self._db.get(models.AIRecommendation, recommendation_id)

    def get_latest_for_event(self, event_id: uuid.UUID) -> models.AIRecommendation | None:
        stmt = (
            select(models.AIRecommendation)
            .where(models.AIRecommendation.event_id == event_id)
            .order_by(models.AIRecommendation.created_at.desc())
            .limit(1)
        )
        return self._db.scalars(stmt).first()

    def update(self, recommendation: models.AIRecommendation) -> models.AIRecommendation:
        self._db.flush()
        return recommendation


class SqlAlchemyEvaluationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, evaluation: models.EvaluationResult) -> models.EvaluationResult:
        self._db.add(evaluation)
        self._db.flush()
        return evaluation

    def get_by_recommendation(self, recommendation_id: uuid.UUID) -> models.EvaluationResult | None:
        stmt = select(models.EvaluationResult).where(
            models.EvaluationResult.recommendation_id == recommendation_id
        )
        return self._db.scalars(stmt).first()


class SqlAlchemyApprovalRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, approval: models.ApprovalDecision) -> models.ApprovalDecision:
        self._db.add(approval)
        self._db.flush()
        return approval

    def get_by_recommendation(self, recommendation_id: uuid.UUID) -> models.ApprovalDecision | None:
        stmt = select(models.ApprovalDecision).where(
            models.ApprovalDecision.recommendation_id == recommendation_id
        )
        return self._db.scalars(stmt).first()


class SqlAlchemyAuditRepository:
    """Hash-chained append-only audit log.

    Each record's hash covers the previous record's hash plus this record's
    canonical payload, so replaying the chain detects any row that was
    edited or deleted out of band. See docs/SECURITY.md for what this does
    and does not guarantee.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def _latest(self) -> models.AuditLog | None:
        stmt = select(models.AuditLog).order_by(models.AuditLog.seq.desc()).limit(1)
        return self._db.scalars(stmt).first()

    @staticmethod
    def _compute_hash(
        previous_hash: str | None, actor: str, action: str, details: dict, event_id: uuid.UUID | None
    ) -> str:
        payload = {
            "previous_hash": previous_hash,
            "actor": actor,
            "action": action,
            "details": details,
            "event_id": str(event_id) if event_id else None,
        }
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def append(
        self, actor: str, action: str, details: dict, event_id: uuid.UUID | None = None
    ) -> models.AuditLog:
        previous = self._latest()
        previous_hash = previous.record_hash if previous else None
        record_hash = self._compute_hash(previous_hash, actor, action, details, event_id)
        entry = models.AuditLog(
            event_id=event_id,
            actor=actor,
            action=action,
            details=details,
            previous_hash=previous_hash,
            record_hash=record_hash,
        )
        self._db.add(entry)
        self._db.flush()
        return entry

    def list_for_event(self, event_id: uuid.UUID) -> list[models.AuditLog]:
        stmt = (
            select(models.AuditLog)
            .where(models.AuditLog.event_id == event_id)
            .order_by(models.AuditLog.seq.asc())
        )
        return list(self._db.scalars(stmt).all())

    def list_all(self, limit: int, offset: int) -> list[models.AuditLog]:
        stmt = select(models.AuditLog).order_by(models.AuditLog.seq.desc()).limit(limit).offset(offset)
        return list(self._db.scalars(stmt).all())

    def verify_chain(self) -> bool:
        stmt = select(models.AuditLog).order_by(models.AuditLog.seq.asc())
        previous_hash: str | None = None
        for entry in self._db.scalars(stmt).all():
            expected = self._compute_hash(
                previous_hash, entry.actor, entry.action, entry.details, entry.event_id
            )
            if expected != entry.record_hash or entry.previous_hash != previous_hash:
                return False
            previous_hash = entry.record_hash
        return True


class SqlAlchemyKillSwitchRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def record_state_change(self, state: str, actor: str, reason: str | None) -> models.KillSwitchEvent:
        entry = models.KillSwitchEvent(state=state, actor=actor, reason=reason)
        self._db.add(entry)
        self._db.flush()
        return entry

    def get_current_state(self) -> models.KillSwitchEvent | None:
        stmt = select(models.KillSwitchEvent).order_by(models.KillSwitchEvent.created_at.desc()).limit(1)
        return self._db.scalars(stmt).first()


class SqlAlchemyProviderEligibilityRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, record: models.ProviderEligibilityRecord) -> models.ProviderEligibilityRecord:
        self._db.add(record)
        self._db.flush()
        return record

    def get_latest(
        self, provider: str, model_name: str, prompt_version: str
    ) -> models.ProviderEligibilityRecord | None:
        stmt = (
            select(models.ProviderEligibilityRecord)
            .where(
                models.ProviderEligibilityRecord.provider == provider,
                models.ProviderEligibilityRecord.model_name == model_name,
                models.ProviderEligibilityRecord.prompt_version == prompt_version,
            )
            .order_by(models.ProviderEligibilityRecord.evaluated_at.desc())
            .limit(1)
        )
        return self._db.scalars(stmt).first()
