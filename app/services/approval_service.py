"""Human approval / rejection of a pending AI recommendation.

Enforces fail-closed behavior: if the kill switch is active at the moment
of approval, the human decision is still recorded (for accountability) but
the simulated action is blocked and the event moves to BLOCKED, never to
ACTION_SIMULATED.
"""

from __future__ import annotations

import uuid

from app.database import models
from app.domain.enums import (
    ApprovalDecisionType,
    AuditAction,
    EventStatus,
    RecommendationFinalStatus,
    RecommendationStatus,
)
from app.domain.exceptions import EntityNotFoundError, InvalidStateTransitionError
from app.domain.workflow import transition
from app.governance.kill_switch import KillSwitchService
from app.repositories.interfaces import (
    ApprovalRepository,
    AuditRepository,
    EventRepository,
    RecommendationRepository,
)
from app.services.action_simulation import simulate_action


class ApprovalService:
    def __init__(
        self,
        recommendation_repo: RecommendationRepository,
        event_repo: EventRepository,
        approval_repo: ApprovalRepository,
        audit_repo: AuditRepository,
        kill_switch: KillSwitchService,
    ) -> None:
        self._recommendations = recommendation_repo
        self._events = event_repo
        self._approvals = approval_repo
        self._audit = audit_repo
        self._kill_switch = kill_switch

    def decide(
        self,
        actor: str,
        recommendation_id: uuid.UUID,
        decision: ApprovalDecisionType,
        reason: str | None,
    ) -> models.ApprovalDecision:
        recommendation = self._recommendations.get(recommendation_id)
        if recommendation is None:
            raise EntityNotFoundError("AIRecommendation", recommendation_id)
        event = self._events.get(recommendation.event_id)
        if event is None:
            raise EntityNotFoundError("OperationalEvent", recommendation.event_id)
        if event.status != EventStatus.PENDING_APPROVAL.value:
            raise InvalidStateTransitionError(event.status, "approval_decision")

        approval = self._approvals.create(
            models.ApprovalDecision(
                recommendation_id=recommendation.id,
                event_id=event.id,
                decision=decision.value,
                approver_identity=actor,
                decision_reason=reason,
            )
        )

        if decision == ApprovalDecisionType.REJECTED:
            recommendation.status = RecommendationStatus.REJECTED.value
            recommendation.final_status = RecommendationFinalStatus.REJECTED.value
            self._recommendations.update(recommendation)
            self._audit.append(
                actor=actor,
                action=AuditAction.APPROVAL_REJECTED.value,
                details={"reason": reason},
                event_id=event.id,
            )
            self._events.update_status(
                event.id, transition(EventStatus.PENDING_APPROVAL, EventStatus.REJECTED)
            )
            return approval

        # APPROVED
        self._audit.append(
            actor=actor,
            action=AuditAction.APPROVAL_GRANTED.value,
            details={"reason": reason},
            event_id=event.id,
        )

        if self._kill_switch.is_active():
            recommendation.status = RecommendationStatus.BLOCKED.value
            recommendation.final_status = RecommendationFinalStatus.BLOCKED.value
            self._recommendations.update(recommendation)
            self._audit.append(
                actor="system",
                action=AuditAction.ACTION_BLOCKED_KILL_SWITCH.value,
                details={"reason": "Kill switch active at simulated-action stage."},
                event_id=event.id,
            )
            self._events.update_status(
                event.id, transition(EventStatus.PENDING_APPROVAL, EventStatus.BLOCKED)
            )
            return approval

        recommendation.status = RecommendationStatus.APPROVED.value
        recommendation.final_status = RecommendationFinalStatus.APPROVED.value
        self._recommendations.update(recommendation)
        self._events.update_status(event.id, transition(EventStatus.PENDING_APPROVAL, EventStatus.APPROVED))

        simulated = simulate_action(recommendation.proposed_action, str(event.id))
        self._audit.append(
            actor="system",
            action=AuditAction.ACTION_SIMULATED.value,
            details=simulated,
            event_id=event.id,
        )
        self._events.update_status(event.id, transition(EventStatus.APPROVED, EventStatus.ACTION_SIMULATED))
        return approval
