"""Operational-event creation, retrieval, and listing."""

from __future__ import annotations

import uuid

from app.database import models
from app.domain.enums import AuditAction, Environment, EventStatus, EventType, SeverityIndicator
from app.domain.exceptions import EntityNotFoundError
from app.repositories.interfaces import AuditRepository, EventRepository


class EventService:
    def __init__(self, event_repo: EventRepository, audit_repo: AuditRepository) -> None:
        self._events = event_repo
        self._audit = audit_repo

    def create_event(
        self,
        actor: str,
        event_type: EventType,
        source: str,
        description: str,
        affected_service: str,
        environment: Environment,
        severity: SeverityIndicator,
        evidence: list[str],
    ) -> models.OperationalEvent:
        event = models.OperationalEvent(
            event_type=event_type.value,
            source=source,
            description=description,
            affected_service=affected_service,
            environment=environment.value,
            severity=severity.value,
            status=EventStatus.OPEN.value,
            evidence=evidence,
        )
        created = self._events.create(event)
        self._audit.append(
            actor=actor,
            action=AuditAction.EVENT_CREATED.value,
            details={
                "event_type": event_type.value,
                "environment": environment.value,
                "severity": severity.value,
                "affected_service": affected_service,
            },
            event_id=created.id,
        )
        return created

    def get_event(self, event_id: uuid.UUID) -> models.OperationalEvent:
        event = self._events.get(event_id)
        if event is None:
            raise EntityNotFoundError("OperationalEvent", event_id)
        return event

    def list_events(
        self,
        limit: int = 50,
        offset: int = 0,
        status: EventStatus | None = None,
        environment: str | None = None,
    ) -> list[models.OperationalEvent]:
        return self._events.list(limit=limit, offset=offset, status=status, environment=environment)
