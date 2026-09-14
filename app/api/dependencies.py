"""FastAPI dependency providers — wires repositories, providers, and
services per-request. This is the composition root for the API layer."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.ai.providers.factory import build_provider
from app.ai.providers.interfaces import AIProvider
from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.governance.identity import require_actor
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


def get_settings_dep() -> Settings:
    return get_settings()


def get_db_session() -> Generator[Session, None, None]:
    yield from get_db()


def get_actor(
    request: Request, x_archguard_actor: str | None = Header(default=None, alias="X-ArchGuard-Actor")
) -> str:
    return require_actor(x_archguard_actor)


def get_event_repo(db: Session = Depends(get_db_session)) -> SqlAlchemyEventRepository:
    return SqlAlchemyEventRepository(db)


def get_risk_repo(db: Session = Depends(get_db_session)) -> SqlAlchemyRiskAssessmentRepository:
    return SqlAlchemyRiskAssessmentRepository(db)


def get_recommendation_repo(db: Session = Depends(get_db_session)) -> SqlAlchemyRecommendationRepository:
    return SqlAlchemyRecommendationRepository(db)


def get_evaluation_repo(db: Session = Depends(get_db_session)) -> SqlAlchemyEvaluationRepository:
    return SqlAlchemyEvaluationRepository(db)


def get_approval_repo(db: Session = Depends(get_db_session)) -> SqlAlchemyApprovalRepository:
    return SqlAlchemyApprovalRepository(db)


def get_audit_repo(db: Session = Depends(get_db_session)) -> SqlAlchemyAuditRepository:
    return SqlAlchemyAuditRepository(db)


def get_kill_switch_repo(db: Session = Depends(get_db_session)) -> SqlAlchemyKillSwitchRepository:
    return SqlAlchemyKillSwitchRepository(db)


def get_eligibility_repo(db: Session = Depends(get_db_session)) -> SqlAlchemyProviderEligibilityRepository:
    return SqlAlchemyProviderEligibilityRepository(db)


def get_provider(settings: Settings = Depends(get_settings_dep)) -> AIProvider:
    return build_provider(settings)


def get_kill_switch_service(
    kill_switch_repo: SqlAlchemyKillSwitchRepository = Depends(get_kill_switch_repo),
    audit_repo: SqlAlchemyAuditRepository = Depends(get_audit_repo),
) -> KillSwitchService:
    return KillSwitchService(kill_switch_repo, audit_repo)


def get_event_service(
    event_repo: SqlAlchemyEventRepository = Depends(get_event_repo),
    audit_repo: SqlAlchemyAuditRepository = Depends(get_audit_repo),
) -> EventService:
    return EventService(event_repo, audit_repo)


def get_risk_assessment_service(
    event_repo: SqlAlchemyEventRepository = Depends(get_event_repo),
    risk_repo: SqlAlchemyRiskAssessmentRepository = Depends(get_risk_repo),
    audit_repo: SqlAlchemyAuditRepository = Depends(get_audit_repo),
) -> RiskAssessmentService:
    return RiskAssessmentService(event_repo, risk_repo, audit_repo)


def get_ai_orchestration_service(
    event_repo: SqlAlchemyEventRepository = Depends(get_event_repo),
    risk_repo: SqlAlchemyRiskAssessmentRepository = Depends(get_risk_repo),
    recommendation_repo: SqlAlchemyRecommendationRepository = Depends(get_recommendation_repo),
    evaluation_repo: SqlAlchemyEvaluationRepository = Depends(get_evaluation_repo),
    approval_repo: SqlAlchemyApprovalRepository = Depends(get_approval_repo),
    audit_repo: SqlAlchemyAuditRepository = Depends(get_audit_repo),
    eligibility_repo: SqlAlchemyProviderEligibilityRepository = Depends(get_eligibility_repo),
    kill_switch: KillSwitchService = Depends(get_kill_switch_service),
    provider: AIProvider = Depends(get_provider),
    settings: Settings = Depends(get_settings_dep),
) -> AIOrchestrationService:
    return AIOrchestrationService(
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


def get_approval_service(
    recommendation_repo: SqlAlchemyRecommendationRepository = Depends(get_recommendation_repo),
    event_repo: SqlAlchemyEventRepository = Depends(get_event_repo),
    approval_repo: SqlAlchemyApprovalRepository = Depends(get_approval_repo),
    audit_repo: SqlAlchemyAuditRepository = Depends(get_audit_repo),
    kill_switch: KillSwitchService = Depends(get_kill_switch_service),
) -> ApprovalService:
    return ApprovalService(recommendation_repo, event_repo, approval_repo, audit_repo, kill_switch)


def get_regression_service(
    eligibility_repo: SqlAlchemyProviderEligibilityRepository = Depends(get_eligibility_repo),
    audit_repo: SqlAlchemyAuditRepository = Depends(get_audit_repo),
) -> RegressionEvaluationService:
    return RegressionEvaluationService(eligibility_repo, audit_repo)
