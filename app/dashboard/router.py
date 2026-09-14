"""Minimal server-rendered dashboard (spec §10).

Read-only by design — all state changes happen through the API (see
README.md for curl examples), which keeps identity/authorization enforcement
in one place instead of duplicating it into an HTML form flow.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.dependencies import (
    get_audit_repo,
    get_eligibility_repo,
    get_evaluation_repo,
    get_event_repo,
    get_event_service,
    get_kill_switch_service,
    get_provider,
    get_recommendation_repo,
    get_risk_repo,
    get_settings_dep,
)
from app.domain.exceptions import EntityNotFoundError
from app.governance.kill_switch import KillSwitchService
from app.repositories.postgres_repositories import (
    SqlAlchemyAuditRepository,
    SqlAlchemyEvaluationRepository,
    SqlAlchemyEventRepository,
    SqlAlchemyProviderEligibilityRepository,
    SqlAlchemyRecommendationRepository,
    SqlAlchemyRiskAssessmentRepository,
)
from app.services.event_service import EventService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("", response_class=HTMLResponse)
def dashboard_home(
    request: Request,
    event_service: EventService = Depends(get_event_service),
    kill_switch: KillSwitchService = Depends(get_kill_switch_service),
    eligibility_repo: SqlAlchemyProviderEligibilityRepository = Depends(get_eligibility_repo),
    provider=Depends(get_provider),
    settings=Depends(get_settings_dep),
) -> HTMLResponse:
    events = event_service.list_events(limit=50)
    eligibility = eligibility_repo.get_latest(
        provider.name, settings.ai_model_name, settings.ai_prompt_version
    )
    return _templates.TemplateResponse(
        request,
        "events_list.html",
        {
            "events": events,
            "kill_switch_state": kill_switch.get_state().value,
            "eligibility": eligibility,
            "provider_name": provider.name,
        },
    )


@router.get("/events/{event_id}", response_class=HTMLResponse)
def dashboard_event_detail(
    request: Request,
    event_id: uuid.UUID,
    event_repo: SqlAlchemyEventRepository = Depends(get_event_repo),
    risk_repo: SqlAlchemyRiskAssessmentRepository = Depends(get_risk_repo),
    recommendation_repo: SqlAlchemyRecommendationRepository = Depends(get_recommendation_repo),
    evaluation_repo: SqlAlchemyEvaluationRepository = Depends(get_evaluation_repo),
    audit_repo: SqlAlchemyAuditRepository = Depends(get_audit_repo),
    kill_switch: KillSwitchService = Depends(get_kill_switch_service),
) -> HTMLResponse:
    event = event_repo.get(event_id)
    if event is None:
        raise EntityNotFoundError("OperationalEvent", event_id)

    risk_assessment = risk_repo.get_latest_for_event(event_id)
    recommendation = recommendation_repo.get_latest_for_event(event_id)
    evaluation = evaluation_repo.get_by_recommendation(recommendation.id) if recommendation else None
    approval = recommendation.approval_decision if recommendation else None
    audit_logs = audit_repo.list_for_event(event_id)

    return _templates.TemplateResponse(
        request,
        "event_detail.html",
        {
            "event": event,
            "risk_assessment": risk_assessment,
            "recommendation": recommendation,
            "evaluation": evaluation,
            "approval": approval,
            "audit_logs": audit_logs,
            "kill_switch_state": kill_switch.get_state().value,
        },
    )
