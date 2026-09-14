from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    get_actor,
    get_ai_orchestration_service,
    get_approval_service,
    get_evaluation_repo,
    get_recommendation_repo,
)
from app.api.schemas import (
    AIRecommendationResponse,
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    EvaluationResultResponse,
)
from app.domain.exceptions import (
    EntityNotFoundError,
    KillSwitchActiveError,
    ProviderNotEligibleError,
    ProviderUnavailableError,
    UnauthorizedActionError,
)
from app.monitoring.metrics import (
    ai_evaluations_total,
    approvals_total,
    blocked_runs_total,
    provider_failures_total,
)
from app.repositories.postgres_repositories import (
    SqlAlchemyEvaluationRepository,
    SqlAlchemyRecommendationRepository,
)
from app.services.ai_orchestration_service import AIOrchestrationService
from app.services.approval_service import ApprovalService

router = APIRouter(tags=["recommendations"])


@router.post(
    "/events/{event_id}/recommendations",
    response_model=AIRecommendationResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_recommendation(
    event_id: uuid.UUID,
    actor: str = Depends(get_actor),
    service: AIOrchestrationService = Depends(get_ai_orchestration_service),
    evaluation_repo: SqlAlchemyEvaluationRepository = Depends(get_evaluation_repo),
) -> AIRecommendationResponse:
    try:
        recommendation = service.request_and_evaluate(actor, event_id)
    except KillSwitchActiveError:
        blocked_runs_total.labels(reason="kill_switch").inc()
        raise
    except ProviderNotEligibleError:
        blocked_runs_total.labels(reason="provider_not_eligible").inc()
        raise
    except ProviderUnavailableError:
        provider_failures_total.inc()
        blocked_runs_total.labels(reason="provider_unavailable").inc()
        raise

    evaluation = evaluation_repo.get_by_recommendation(recommendation.id)
    if evaluation is not None:
        ai_evaluations_total.labels(result=evaluation.overall_result).inc()
        if evaluation.overall_result == "failed":
            blocked_runs_total.labels(reason="evaluation_failed").inc()
    return AIRecommendationResponse.model_validate(recommendation)


@router.get("/recommendations/{recommendation_id}", response_model=AIRecommendationResponse)
def get_recommendation(
    recommendation_id: uuid.UUID,
    recommendation_repo: SqlAlchemyRecommendationRepository = Depends(get_recommendation_repo),
) -> AIRecommendationResponse:
    recommendation = recommendation_repo.get(recommendation_id)
    if recommendation is None:
        raise EntityNotFoundError("AIRecommendation", recommendation_id)
    return AIRecommendationResponse.model_validate(recommendation)


@router.get("/events/{event_id}/recommendations/latest", response_model=AIRecommendationResponse)
def get_latest_recommendation(
    event_id: uuid.UUID,
    recommendation_repo: SqlAlchemyRecommendationRepository = Depends(get_recommendation_repo),
) -> AIRecommendationResponse:
    recommendation = recommendation_repo.get_latest_for_event(event_id)
    if recommendation is None:
        raise EntityNotFoundError("AIRecommendation", f"for event {event_id}")
    return AIRecommendationResponse.model_validate(recommendation)


@router.get("/recommendations/{recommendation_id}/evaluation", response_model=EvaluationResultResponse)
def get_evaluation(
    recommendation_id: uuid.UUID,
    evaluation_repo: SqlAlchemyEvaluationRepository = Depends(get_evaluation_repo),
) -> EvaluationResultResponse:
    evaluation = evaluation_repo.get_by_recommendation(recommendation_id)
    if evaluation is None:
        raise EntityNotFoundError("EvaluationResult", f"for recommendation {recommendation_id}")
    return EvaluationResultResponse.model_validate(evaluation)


@router.post(
    "/recommendations/{recommendation_id}/approval",
    response_model=ApprovalDecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def decide_approval(
    recommendation_id: uuid.UUID,
    payload: ApprovalDecisionRequest,
    actor: str = Depends(get_actor),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalDecisionResponse:
    # Lightweight authorization: only "approver:*" or "admin:*" identities may decide.
    if not actor.startswith(("approver:", "admin:")):
        raise UnauthorizedActionError(
            f"Actor '{actor}' is not authorized to approve or reject recommendations "
            "(requires 'approver:' or 'admin:' role prefix)."
        )
    decision = service.decide(actor, recommendation_id, payload.decision, payload.reason)
    approvals_total.labels(outcome=payload.decision.value).inc()
    return ApprovalDecisionResponse.model_validate(decision)
