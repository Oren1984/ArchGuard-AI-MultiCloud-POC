from __future__ import annotations

import pytest

from app.domain.enums import EventStatus
from app.domain.exceptions import InvalidStateTransitionError
from app.domain.workflow import TERMINAL_STATES, can_transition, transition


def test_open_to_risk_assessed_is_valid():
    assert can_transition(EventStatus.OPEN, EventStatus.RISK_ASSESSED)
    assert transition(EventStatus.OPEN, EventStatus.RISK_ASSESSED) == EventStatus.RISK_ASSESSED


def test_open_cannot_skip_directly_to_approved():
    assert not can_transition(EventStatus.OPEN, EventStatus.APPROVED)
    with pytest.raises(InvalidStateTransitionError):
        transition(EventStatus.OPEN, EventStatus.APPROVED)


@pytest.mark.parametrize("terminal", list(TERMINAL_STATES))
def test_terminal_states_have_no_outgoing_transitions(terminal):
    assert can_transition(terminal, EventStatus.OPEN) is False


def test_full_approval_path():
    state = EventStatus.OPEN
    for target in (
        EventStatus.RISK_ASSESSED,
        EventStatus.RECOMMENDATION_EVALUATED,
        EventStatus.PENDING_APPROVAL,
        EventStatus.APPROVED,
        EventStatus.ACTION_SIMULATED,
    ):
        state = transition(state, target)
    assert state == EventStatus.ACTION_SIMULATED
    assert state in TERMINAL_STATES


def test_rejection_path_is_terminal():
    state = transition(EventStatus.PENDING_APPROVAL, EventStatus.REJECTED)
    assert state in TERMINAL_STATES


def test_blocked_reachable_from_risk_assessed_and_pending_approval():
    assert can_transition(EventStatus.RISK_ASSESSED, EventStatus.BLOCKED)
    assert can_transition(EventStatus.PENDING_APPROVAL, EventStatus.BLOCKED)
    assert can_transition(EventStatus.APPROVED, EventStatus.BLOCKED)
