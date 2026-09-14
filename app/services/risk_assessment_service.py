"""Runs the deterministic risk engine against an event and persists the
result. Works with the AI provider unavailable — no dependency on it."""

from __future__ import annotations

import uuid

from app.database import models
from app.domain.enums import AuditAction, Environment, EventStatus, EventType, SeverityIndicator
from app.domain.risk_engine import RiskEngine, RiskInput
from app.domain.workflow import transition
from app.repositories.interfaces import AuditRepository, EventRepository, RiskAssessmentRepository
from app.services.event_service import EventService


class RiskAssessmentService:
    def __init__(
        self,
        event_repo: EventRepository,
        risk_repo: RiskAssessmentRepository,
        audit_repo: AuditRepository,
        engine: RiskEngine | None = None,
    ) -> None:
        self._events = event_repo
        self._risk = risk_repo
        self._audit = audit_repo
        self._engine = engine or RiskEngine()

    def assess(self, actor: str, event_id: uuid.UUID) -> models.RiskAssessment:
        event = EventService(self._events, self._audit).get_event(event_id)

        risk_input = RiskInput(
            event_type=EventType(event.event_type),
            environment=Environment(event.environment),
            severity=SeverityIndicator(event.severity),
            affected_service=event.affected_service,
            description=event.description,
            evidence_count=len(event.evidence or []),
        )
        risk_score = self._engine.assess(risk_input)

        assessment = models.RiskAssessment(
            event_id=event.id,
            score=risk_score.score,
            level=risk_score.level.value,
            triggered_rules=[
                {
                    "rule_id": r.rule_id,
                    "description": r.description,
                    "points": r.points,
                    "category": r.category,
                }
                for r in risk_score.triggered_rules
            ],
            explanation=risk_score.explanation,
            engine_version=self._engine.engine_version,
        )
        created = self._risk.create(assessment)

        if event.status == EventStatus.OPEN.value:
            new_status = transition(EventStatus.OPEN, EventStatus.RISK_ASSESSED)
            self._events.update_status(event.id, new_status)

        self._audit.append(
            actor=actor,
            action=AuditAction.RISK_ASSESSED.value,
            details={
                "score": risk_score.score,
                "level": risk_score.level.value,
                "rule_count": len(risk_score.triggered_rules),
            },
            event_id=event.id,
        )
        return created

    def get_latest(self, event_id: uuid.UUID) -> models.RiskAssessment | None:
        return self._risk.get_latest_for_event(event_id)
