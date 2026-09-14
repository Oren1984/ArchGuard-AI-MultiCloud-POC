"""Local kill switch. Provider-independent, database-backed on/off latch that
fails closed: AI processing and simulated-action progression are blocked
whenever it is active (spec §6.5, §8).
"""

from __future__ import annotations

from app.database.models import KillSwitchEvent
from app.domain.enums import AuditAction, KillSwitchState
from app.repositories.interfaces import AuditRepository, KillSwitchRepository


class KillSwitchService:
    def __init__(self, repo: KillSwitchRepository, audit_repo: AuditRepository) -> None:
        self._repo = repo
        self._audit = audit_repo

    def get_current_event(self) -> KillSwitchEvent | None:
        return self._repo.get_current_state()

    def get_state(self) -> KillSwitchState:
        current = self._repo.get_current_state()
        if current is None:
            return KillSwitchState.INACTIVE
        return KillSwitchState(current.state)

    def is_active(self) -> bool:
        return self.get_state() == KillSwitchState.ACTIVE

    def activate(self, actor: str, reason: str | None) -> KillSwitchState:
        self._repo.record_state_change(KillSwitchState.ACTIVE.value, actor, reason)
        self._audit.append(
            actor=actor,
            action=AuditAction.KILL_SWITCH_ACTIVATED.value,
            details={"reason": reason},
        )
        return KillSwitchState.ACTIVE

    def deactivate(self, actor: str, reason: str | None) -> KillSwitchState:
        self._repo.record_state_change(KillSwitchState.INACTIVE.value, actor, reason)
        self._audit.append(
            actor=actor,
            action=AuditAction.KILL_SWITCH_DEACTIVATED.value,
            details={"reason": reason},
        )
        return KillSwitchState.INACTIVE
