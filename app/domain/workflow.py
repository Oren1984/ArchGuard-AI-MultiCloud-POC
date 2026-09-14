"""Explicit event workflow state machine.

Encodes the mandatory flow from the spec:
  Input -> Risk Assessment -> AI/Mock Recommendation -> Automated Evaluation
  -> Risk Classification -> Human Approval at Defined Risk Points
  -> Simulated Next Stage or Blocked State

This module has no dependency on FastAPI, SQLAlchemy, or any cloud/AI
provider — it is pure business logic and is exercised directly by unit tests.
"""

from __future__ import annotations

from app.domain.enums import EventStatus
from app.domain.exceptions import InvalidStateTransitionError

VALID_TRANSITIONS: dict[EventStatus, frozenset[EventStatus]] = {
    EventStatus.OPEN: frozenset({EventStatus.RISK_ASSESSED}),
    EventStatus.RISK_ASSESSED: frozenset({EventStatus.RECOMMENDATION_EVALUATED, EventStatus.BLOCKED}),
    EventStatus.RECOMMENDATION_EVALUATED: frozenset(
        {EventStatus.PENDING_APPROVAL, EventStatus.BLOCKED, EventStatus.ACTION_SIMULATED}
    ),
    EventStatus.PENDING_APPROVAL: frozenset(
        {EventStatus.APPROVED, EventStatus.REJECTED, EventStatus.BLOCKED}
    ),
    EventStatus.APPROVED: frozenset({EventStatus.ACTION_SIMULATED, EventStatus.BLOCKED}),
    EventStatus.REJECTED: frozenset(),
    EventStatus.BLOCKED: frozenset(),
    EventStatus.ACTION_SIMULATED: frozenset(),
}

TERMINAL_STATES: frozenset[EventStatus] = frozenset(
    {EventStatus.REJECTED, EventStatus.BLOCKED, EventStatus.ACTION_SIMULATED}
)


def can_transition(current: EventStatus, target: EventStatus) -> bool:
    return target in VALID_TRANSITIONS.get(current, frozenset())


def transition(current: EventStatus, target: EventStatus) -> EventStatus:
    if not can_transition(current, target):
        raise InvalidStateTransitionError(current.value, target.value)
    return target
