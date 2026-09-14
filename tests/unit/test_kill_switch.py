from __future__ import annotations

from app.database import models
from app.domain.enums import KillSwitchState
from app.governance.kill_switch import KillSwitchService


class _FakeKillSwitchRepo:
    def __init__(self) -> None:
        self._events: list[models.KillSwitchEvent] = []

    def record_state_change(self, state: str, actor: str, reason: str | None) -> models.KillSwitchEvent:
        event = models.KillSwitchEvent(state=state, actor=actor, reason=reason)
        self._events.append(event)
        return event

    def get_current_state(self) -> models.KillSwitchEvent | None:
        return self._events[-1] if self._events else None


class _FakeAuditRepo:
    def __init__(self) -> None:
        self.entries: list[dict] = []

    def append(self, actor, action, details, event_id=None):
        self.entries.append({"actor": actor, "action": action, "details": details, "event_id": event_id})


def test_default_state_is_inactive_with_no_events():
    service = KillSwitchService(_FakeKillSwitchRepo(), _FakeAuditRepo())
    assert service.get_state() == KillSwitchState.INACTIVE
    assert service.is_active() is False


def test_activate_flips_state_and_records_audit():
    kill_repo = _FakeKillSwitchRepo()
    audit_repo = _FakeAuditRepo()
    service = KillSwitchService(kill_repo, audit_repo)

    service.activate("admin:oncall", "drill")

    assert service.get_state() == KillSwitchState.ACTIVE
    assert service.is_active() is True
    assert audit_repo.entries[-1]["action"] == "kill_switch_activated"


def test_deactivate_after_activate_restores_inactive():
    kill_repo = _FakeKillSwitchRepo()
    audit_repo = _FakeAuditRepo()
    service = KillSwitchService(kill_repo, audit_repo)

    service.activate("admin:oncall", "drill")
    service.deactivate("admin:oncall", "drill over")

    assert service.get_state() == KillSwitchState.INACTIVE
    assert audit_repo.entries[-1]["action"] == "kill_switch_deactivated"
