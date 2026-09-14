"""Non-HTTP composition root: builds the full service graph from a plain
SQLAlchemy Session. Used by the seed script and integration/e2e tests so the
wiring isn't duplicated between FastAPI DI (app/api/dependencies.py) and
script/test contexts.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.providers.factory import build_provider
from app.ai.providers.interfaces import AIProvider
from app.core.config import Settings, get_settings
from app.governance.kill_switch import KillSwitchService
from app.repositories.postgres_repositories import (
    SqlAlchemyApprovalRepository,
    SqlAlchemyAuditRepository,
    SqlAlchemyEvaluationRepository,
    SqlAlchemyEventRepository,
    SqlAlchemyKillSwitchRepository,
    SqlAlchemyProviderEligibilityRepository,
    SqlAlchemyRecommendationRepository,
    SqlAlchemyRiskAssessmentRepository,
)
from app.services.ai_orchestration_service import AIOrchestrationService
from app.services.approval_service import ApprovalService
from app.services.event_service import EventService
from app.services.regression_evaluation_service import RegressionEvaluationService
from app.services.risk_assessment_service import RiskAssessmentService


@dataclass
class ServiceContainer:
    settings: Settings
    provider: AIProvider
    event_repo: SqlAlchemyEventRepository
    risk_repo: SqlAlchemyRiskAssessmentRepository
    recommendation_repo: SqlAlchemyRecommendationRepository
    evaluation_repo: SqlAlchemyEvaluationRepository
    approval_repo: SqlAlchemyApprovalRepository
    audit_repo: SqlAlchemyAuditRepository
    eligibility_repo: SqlAlchemyProviderEligibilityRepository
    kill_switch_repo: SqlAlchemyKillSwitchRepository
    kill_switch: KillSwitchService
    event_service: EventService
    risk_service: RiskAssessmentService
    ai_service: AIOrchestrationService
    approval_service: ApprovalService
    regression_service: RegressionEvaluationService


def build_services(
    db: Session, settings: Settings | None = None, provider: AIProvider | None = None
) -> ServiceContainer:
    settings = settings or get_settings()
    provider = provider or build_provider(settings)

    event_repo = SqlAlchemyEventRepository(db)
    risk_repo = SqlAlchemyRiskAssessmentRepository(db)
    recommendation_repo = SqlAlchemyRecommendationRepository(db)
    evaluation_repo = SqlAlchemyEvaluationRepository(db)
    approval_repo = SqlAlchemyApprovalRepository(db)
    audit_repo = SqlAlchemyAuditRepository(db)
    eligibility_repo = SqlAlchemyProviderEligibilityRepository(db)
    kill_switch_repo = SqlAlchemyKillSwitchRepository(db)

    kill_switch = KillSwitchService(kill_switch_repo, audit_repo)
    event_service = EventService(event_repo, audit_repo)
    risk_service = RiskAssessmentService(event_repo, risk_repo, audit_repo)
    ai_service = AIOrchestrationService(
        event_repo,
        risk_repo,
        recommendation_repo,
        evaluation_repo,
        approval_repo,
        audit_repo,
        eligibility_repo,
        kill_switch,
        provider,
        settings,
    )
    approval_service = ApprovalService(
        recommendation_repo, event_repo, approval_repo, audit_repo, kill_switch
    )
    regression_service = RegressionEvaluationService(eligibility_repo, audit_repo)

    return ServiceContainer(
        settings=settings,
        provider=provider,
        event_repo=event_repo,
        risk_repo=risk_repo,
        recommendation_repo=recommendation_repo,
        evaluation_repo=evaluation_repo,
        approval_repo=approval_repo,
        audit_repo=audit_repo,
        eligibility_repo=eligibility_repo,
        kill_switch_repo=kill_switch_repo,
        kill_switch=kill_switch,
        event_service=event_service,
        risk_service=risk_service,
        ai_service=ai_service,
        approval_service=approval_service,
        regression_service=regression_service,
    )
