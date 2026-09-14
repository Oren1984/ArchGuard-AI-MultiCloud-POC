"""Orchestrates the mandatory flow from spec §8:

  AI/Mock Recommendation -> Automated Evaluation -> Risk Classification
  -> (Human Approval | Auto-clear | Blocked)

This is the only service that talks to an AIProvider. It never trusts raw
provider output directly — everything passes through the evaluation gates
in app/ai/evaluation/ before a routing decision is made by
app/governance/approval_gate.py.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict

from app.ai.evaluation.confidence_evaluator import evaluate_confidence
from app.ai.evaluation.consistency_evaluator import evaluate_consistency
from app.ai.evaluation.grounding_evaluator import evaluate_grounding
from app.ai.evaluation.safety_evaluator import evaluate_safety
from app.ai.evaluation.schema_validator import validate_schema
from app.ai.providers.interfaces import AIProvider, RecommendationRequest
from app.core.config import Settings
from app.database import models
from app.domain.enums import (
    ApprovalDecisionType,
    AuditAction,
    CheckResult,
    EventStatus,
    ProposedActionType,
    RecommendationFinalStatus,
    RecommendationStatus,
    RiskLevel,
)
from app.domain.exceptions import (
    EntityNotFoundError,
    InvalidStateTransitionError,
    KillSwitchActiveError,
    ProviderNotEligibleError,
    ProviderUnavailableError,
)
from app.domain.workflow import transition
from app.governance.approval_gate import decide_routing
from app.governance.kill_switch import KillSwitchService
from app.repositories.interfaces import (
    AuditRepository,
    EvaluationRepository,
    EventRepository,
    ProviderEligibilityRepository,
    RecommendationRepository,
    RiskAssessmentRepository,
)
from app.services.action_simulation import simulate_action

_SAFE_FALLBACK_ACTION = ProposedActionType.ESCALATE_TO_HUMAN.value


class AIOrchestrationService:
    def __init__(
        self,
        event_repo: EventRepository,
        risk_repo: RiskAssessmentRepository,
        recommendation_repo: RecommendationRepository,
        evaluation_repo: EvaluationRepository,
        approval_repo,
        audit_repo: AuditRepository,
        eligibility_repo: ProviderEligibilityRepository,
        kill_switch: KillSwitchService,
        provider: AIProvider,
        settings: Settings,
    ) -> None:
        self._events = event_repo
        self._risk = risk_repo
        self._recommendations = recommendation_repo
        self._evaluations = evaluation_repo
        self._approvals = approval_repo
        self._audit = audit_repo
        self._eligibility = eligibility_repo
        self._kill_switch = kill_switch
        self._provider = provider
        self._settings = settings

    def request_and_evaluate(self, actor: str, event_id: uuid.UUID) -> models.AIRecommendation:
        event = self._events.get(event_id)
        if event is None:
            raise EntityNotFoundError("OperationalEvent", event_id)
        if event.status != EventStatus.RISK_ASSESSED.value:
            raise InvalidStateTransitionError(event.status, EventStatus.RECOMMENDATION_EVALUATED.value)

        risk_assessment = self._risk.get_latest_for_event(event_id)
        if risk_assessment is None:
            raise InvalidStateTransitionError(event.status, "risk_assessment_required")

        if self._kill_switch.is_active():
            self._audit.append(
                actor=actor,
                action=AuditAction.AI_RECOMMENDATION_BLOCKED_KILL_SWITCH.value,
                details={"reason": "Kill switch active before AI provider call."},
                event_id=event.id,
            )
            self._events.update_status(event.id, transition(EventStatus.RISK_ASSESSED, EventStatus.BLOCKED))
            raise KillSwitchActiveError("ai_recommendation_request")

        eligibility = self._eligibility.get_latest(
            self._provider.name, self._settings.ai_model_name, self._settings.ai_prompt_version
        )
        if eligibility is None or not eligibility.eligible:
            self._audit.append(
                actor=actor,
                action=AuditAction.AI_RECOMMENDATION_REQUESTED.value,
                details={
                    "blocked_reason": "provider_not_eligible",
                    "provider": self._provider.name,
                    "model": self._settings.ai_model_name,
                },
                event_id=event.id,
            )
            raise ProviderNotEligibleError(self._provider.name, self._settings.ai_model_name)

        request = RecommendationRequest(
            event_id=str(event.id),
            event_type=event.event_type,
            environment=event.environment,
            severity=event.severity,
            affected_service=event.affected_service,
            description=event.description,
            evidence=tuple(event.evidence or []),
            risk_score=risk_assessment.score,
            risk_level=risk_assessment.level,
            prompt_version=self._settings.ai_prompt_version,
        )

        self._audit.append(
            actor=actor,
            action=AuditAction.AI_RECOMMENDATION_REQUESTED.value,
            details={"provider": self._provider.name, "prompt_version": self._settings.ai_prompt_version},
            event_id=event.id,
        )

        try:
            response = self._provider.generate_recommendation(request)
        except ProviderUnavailableError as exc:
            recommendation = self._recommendations.create(
                models.AIRecommendation(
                    event_id=event.id,
                    risk_assessment_id=risk_assessment.id,
                    provider=self._provider.name,
                    model_name=self._settings.ai_model_name,
                    model_version=None,
                    prompt_version=self._settings.ai_prompt_version,
                    input_reference=asdict(request),
                    summary="",
                    suggested_response="",
                    evidence_references=[],
                    confidence=0.0,
                    proposed_action=_SAFE_FALLBACK_ACTION,
                    risk_notes=str(exc),
                    requires_human_approval=True,
                    raw_output={"error": str(exc)},
                    status=RecommendationStatus.ERROR.value,
                    final_status=RecommendationFinalStatus.BLOCKED.value,
                )
            )
            self._audit.append(
                actor=actor,
                action=AuditAction.AI_PROVIDER_FAILURE.value,
                details={"provider": self._provider.name, "error": str(exc)},
                event_id=event.id,
            )
            self._events.update_status(event.id, transition(EventStatus.RISK_ASSESSED, EventStatus.BLOCKED))
            raise

        schema_outcome = validate_schema(response.raw_output)

        if not schema_outcome.valid or schema_outcome.parsed is None:
            recommendation = self._recommendations.create(
                models.AIRecommendation(
                    event_id=event.id,
                    risk_assessment_id=risk_assessment.id,
                    provider=self._provider.name,
                    model_name=response.model_name,
                    model_version=response.model_version,
                    prompt_version=self._settings.ai_prompt_version,
                    input_reference=asdict(request),
                    summary=str(response.raw_output.get("summary", "")),
                    suggested_response=str(response.raw_output.get("suggested_response", "")),
                    evidence_references=list(response.raw_output.get("evidence_references", []) or []),
                    confidence=0.0,
                    proposed_action=_SAFE_FALLBACK_ACTION,
                    risk_notes="Schema validation failed; remaining checks skipped.",
                    requires_human_approval=True,
                    raw_output=response.raw_output,
                    status=RecommendationStatus.BLOCKED.value,
                    final_status=RecommendationFinalStatus.BLOCKED.value,
                )
            )
            self._evaluations.create(
                models.EvaluationResult(
                    recommendation_id=recommendation.id,
                    schema_valid=False,
                    grounding_result=CheckResult.FAILED.value,
                    grounding_notes="Skipped: schema invalid.",
                    confidence_result=CheckResult.FAILED.value,
                    confidence_value=0.0,
                    safety_result=CheckResult.FAILED.value,
                    safety_notes="Skipped: schema invalid.",
                    consistency_result=CheckResult.FAILED.value,
                    consistency_notes="Skipped: schema invalid.",
                    overall_result=CheckResult.FAILED.value,
                    risk_classification=risk_assessment.level,
                    requires_approval=False,
                    evaluation_summary=f"Schema validation failed: {schema_outcome.error} Recommendation blocked.",
                )
            )
            self._audit.append(
                actor=actor,
                action=AuditAction.EVALUATION_COMPLETED.value,
                details={"overall_result": CheckResult.FAILED.value, "reason": "schema_invalid"},
                event_id=event.id,
            )
            self._events.update_status(event.id, transition(EventStatus.RISK_ASSESSED, EventStatus.BLOCKED))
            return recommendation

        parsed = schema_outcome.parsed
        grounding = evaluate_grounding(
            parsed.evidence_references, list(event.evidence or []), event.description
        )
        confidence_check = evaluate_confidence(parsed.confidence, self._settings.eval_min_confidence)
        safety = evaluate_safety(parsed.proposed_action)
        consistency = evaluate_consistency(
            self._provider,
            request,
            parsed.proposed_action,
            parsed.confidence,
            max(self._settings.eval_consistency_runs - 1, 0),
        )

        check_results = [grounding.result, confidence_check.result, safety.result, consistency.result]
        if CheckResult.FAILED in check_results:
            overall = CheckResult.FAILED
        elif CheckResult.WARNING in check_results:
            overall = CheckResult.WARNING
        else:
            overall = CheckResult.PASSED

        base_risk_level = RiskLevel(risk_assessment.level)
        risk_classification = RiskLevel.CRITICAL if safety.result == CheckResult.FAILED else base_risk_level

        kill_switch_active_now = self._kill_switch.is_active()
        decision = decide_routing(
            risk_classification, overall, parsed.requires_human_approval, kill_switch_active_now
        )

        if decision.blocked:
            rec_status = RecommendationStatus.BLOCKED
            final_status = RecommendationFinalStatus.BLOCKED
        elif decision.requires_approval:
            rec_status = RecommendationStatus.PENDING_APPROVAL
            final_status = RecommendationFinalStatus.PENDING
        else:
            rec_status = RecommendationStatus.EVALUATED
            final_status = RecommendationFinalStatus.PENDING

        recommendation = self._recommendations.create(
            models.AIRecommendation(
                event_id=event.id,
                risk_assessment_id=risk_assessment.id,
                provider=self._provider.name,
                model_name=response.model_name,
                model_version=response.model_version,
                prompt_version=self._settings.ai_prompt_version,
                input_reference=asdict(request),
                summary=parsed.summary,
                suggested_response=parsed.suggested_response,
                evidence_references=parsed.evidence_references,
                confidence=parsed.confidence,
                proposed_action=parsed.proposed_action,
                risk_notes=parsed.risk_notes,
                requires_human_approval=parsed.requires_human_approval,
                raw_output=response.raw_output,
                status=rec_status.value,
                final_status=final_status.value,
            )
        )

        summary_text = (
            f"Overall: {overall.value}. Grounding: {grounding.notes} Confidence: {confidence_check.notes} "
            f"Safety: {safety.notes} Consistency: {consistency.notes}"
        )
        if decision.blocked:
            summary_text += f" ROUTING: BLOCKED ({decision.block_reason})"
        elif decision.requires_approval:
            summary_text += " ROUTING: PENDING_APPROVAL"
        else:
            summary_text += " ROUTING: AUTO_CLEAR"

        self._evaluations.create(
            models.EvaluationResult(
                recommendation_id=recommendation.id,
                schema_valid=True,
                grounding_result=grounding.result.value,
                grounding_notes=grounding.notes,
                confidence_result=confidence_check.result.value,
                confidence_value=parsed.confidence,
                safety_result=safety.result.value,
                safety_notes=safety.notes,
                consistency_result=consistency.result.value,
                consistency_notes=consistency.notes,
                overall_result=overall.value,
                risk_classification=risk_classification.value,
                requires_approval=decision.requires_approval,
                evaluation_summary=summary_text,
            )
        )
        self._audit.append(
            actor=actor,
            action=AuditAction.EVALUATION_COMPLETED.value,
            details={
                "overall_result": overall.value,
                "risk_classification": risk_classification.value,
                "requires_approval": decision.requires_approval,
                "blocked": decision.blocked,
            },
            event_id=event.id,
        )

        self._events.update_status(
            event.id, transition(EventStatus.RISK_ASSESSED, EventStatus.RECOMMENDATION_EVALUATED)
        )

        if decision.blocked:
            self._events.update_status(
                event.id, transition(EventStatus.RECOMMENDATION_EVALUATED, EventStatus.BLOCKED)
            )
        elif decision.requires_approval:
            self._events.update_status(
                event.id, transition(EventStatus.RECOMMENDATION_EVALUATED, EventStatus.PENDING_APPROVAL)
            )
        else:
            self._auto_clear(actor, event, recommendation)

        return recommendation

    def _auto_clear(
        self, actor: str, event: models.OperationalEvent, recommendation: models.AIRecommendation
    ) -> None:
        """No-approval-required path: system auto-clears and simulates the
        action, still producing a full, uniform audit/approval trail."""
        if self._kill_switch.is_active():
            recommendation.status = RecommendationStatus.BLOCKED.value
            recommendation.final_status = RecommendationFinalStatus.BLOCKED.value
            self._recommendations.update(recommendation)
            self._audit.append(
                actor=actor,
                action=AuditAction.ACTION_BLOCKED_KILL_SWITCH.value,
                details={"reason": "Kill switch active at simulated-action stage."},
                event_id=event.id,
            )
            self._events.update_status(
                event.id, transition(EventStatus.RECOMMENDATION_EVALUATED, EventStatus.BLOCKED)
            )
            return

        self._approvals.create(
            models.ApprovalDecision(
                recommendation_id=recommendation.id,
                event_id=event.id,
                decision=ApprovalDecisionType.APPROVED.value,
                approver_identity="system:auto-clear",
                decision_reason=(
                    "Auto-cleared: risk classification and evaluation result did not require "
                    "human approval under current policy."
                ),
            )
        )
        recommendation.status = RecommendationStatus.APPROVED.value
        recommendation.final_status = RecommendationFinalStatus.APPROVED.value
        self._recommendations.update(recommendation)

        self._audit.append(
            actor="system:auto-clear",
            action=AuditAction.APPROVAL_GRANTED.value,
            details={"mode": "auto-clear"},
            event_id=event.id,
        )

        simulated = simulate_action(recommendation.proposed_action, str(event.id))
        self._audit.append(
            actor="system",
            action=AuditAction.ACTION_SIMULATED.value,
            details=simulated,
            event_id=event.id,
        )
        self._events.update_status(
            event.id, transition(EventStatus.RECOMMENDATION_EVALUATED, EventStatus.ACTION_SIMULATED)
        )
