from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.ai.providers.interfaces import AIProvider
from app.api.dependencies import (
    get_actor,
    get_eligibility_repo,
    get_provider,
    get_regression_service,
    get_settings_dep,
)
from app.api.schemas import ProviderEligibilityResponse, RegressionEvaluationRequest
from app.core.config import Settings
from app.domain.exceptions import EntityNotFoundError
from app.repositories.postgres_repositories import SqlAlchemyProviderEligibilityRepository
from app.services.regression_evaluation_service import RegressionEvaluationService

router = APIRouter(prefix="/providers", tags=["providers"])


@router.post(
    "/regression-evaluation", response_model=ProviderEligibilityResponse, status_code=status.HTTP_201_CREATED
)
def run_regression_evaluation(
    payload: RegressionEvaluationRequest,
    actor: str = Depends(get_actor),
    provider: AIProvider = Depends(get_provider),
    settings: Settings = Depends(get_settings_dep),
    service: RegressionEvaluationService = Depends(get_regression_service),
) -> ProviderEligibilityResponse:
    model_name = payload.model_name or settings.ai_model_name
    prompt_version = payload.prompt_version or settings.ai_prompt_version
    record = service.run(actor, provider, model_name, prompt_version)
    return ProviderEligibilityResponse.model_validate(record)


@router.get("/eligibility", response_model=ProviderEligibilityResponse)
def get_provider_eligibility(
    provider: AIProvider = Depends(get_provider),
    settings: Settings = Depends(get_settings_dep),
    eligibility_repo: SqlAlchemyProviderEligibilityRepository = Depends(get_eligibility_repo),
) -> ProviderEligibilityResponse:
    record = eligibility_repo.get_latest(provider.name, settings.ai_model_name, settings.ai_prompt_version)
    if record is None:
        raise EntityNotFoundError("ProviderEligibilityRecord", f"{provider.name}/{settings.ai_model_name}")
    return ProviderEligibilityResponse.model_validate(record)
