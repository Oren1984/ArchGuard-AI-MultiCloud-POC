from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_actor, get_event_service, get_risk_assessment_service
from app.api.schemas import EventCreateRequest, EventResponse, RiskAssessmentResponse
from app.domain.enums import Environment, EventStatus
from app.domain.exceptions import EntityNotFoundError
from app.monitoring.metrics import events_created_total, risk_assessments_total
from app.services.event_service import EventService
from app.services.risk_assessment_service import RiskAssessmentService

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreateRequest,
    actor: str = Depends(get_actor),
    service: EventService = Depends(get_event_service),
) -> EventResponse:
    event = service.create_event(
        actor=actor,
        event_type=payload.event_type,
        source=payload.source,
        description=payload.description,
        affected_service=payload.affected_service,
        environment=payload.environment,
        severity=payload.severity,
        evidence=payload.evidence,
    )
    events_created_total.inc()
    return EventResponse.model_validate(event)


@router.get("", response_model=list[EventResponse])
def list_events(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: EventStatus | None = Query(default=None, alias="status"),
    environment: Environment | None = Query(default=None),
    service: EventService = Depends(get_event_service),
) -> list[EventResponse]:
    events = service.list_events(
        limit=limit,
        offset=offset,
        status=status_filter,
        environment=environment.value if environment else None,
    )
    return [EventResponse.model_validate(e) for e in events]


@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: uuid.UUID, service: EventService = Depends(get_event_service)) -> EventResponse:
    return EventResponse.model_validate(service.get_event(event_id))


@router.post(
    "/{event_id}/risk-assessment", response_model=RiskAssessmentResponse, status_code=status.HTTP_201_CREATED
)
def run_risk_assessment(
    event_id: uuid.UUID,
    actor: str = Depends(get_actor),
    service: RiskAssessmentService = Depends(get_risk_assessment_service),
) -> RiskAssessmentResponse:
    assessment = service.assess(actor, event_id)
    risk_assessments_total.inc()
    return RiskAssessmentResponse.model_validate(assessment)


@router.get("/{event_id}/risk-assessment", response_model=RiskAssessmentResponse)
def get_risk_assessment(
    event_id: uuid.UUID, service: RiskAssessmentService = Depends(get_risk_assessment_service)
) -> RiskAssessmentResponse:
    assessment = service.get_latest(event_id)
    if assessment is None:
        raise EntityNotFoundError("RiskAssessment", f"for event {event_id}")
    return RiskAssessmentResponse.model_validate(assessment)
