from __future__ import annotations

from fastapi import APIRouter, Depends, Header, status

from app.api.dependencies import get_kill_switch_service
from app.api.schemas import KillSwitchStateResponse, KillSwitchToggleRequest
from app.governance.identity import require_role
from app.governance.kill_switch import KillSwitchService

router = APIRouter(prefix="/governance/kill-switch", tags=["governance"])


def _admin_actor(x_archguard_actor: str | None = Header(default=None, alias="X-ArchGuard-Actor")) -> str:
    return require_role(x_archguard_actor or "", allowed_prefixes=("admin:",))


@router.get("", response_model=KillSwitchStateResponse)
def get_kill_switch_state(
    service: KillSwitchService = Depends(get_kill_switch_service),
) -> KillSwitchStateResponse:
    current = service.get_current_event()
    if current is None:
        return KillSwitchStateResponse(state=service.get_state())
    return KillSwitchStateResponse(
        state=service.get_state(), actor=current.actor, reason=current.reason, changed_at=current.created_at
    )


@router.post("/activate", response_model=KillSwitchStateResponse, status_code=status.HTTP_201_CREATED)
def activate_kill_switch(
    payload: KillSwitchToggleRequest,
    actor: str = Depends(_admin_actor),
    service: KillSwitchService = Depends(get_kill_switch_service),
) -> KillSwitchStateResponse:
    state = service.activate(actor, payload.reason)
    return KillSwitchStateResponse(state=state, actor=actor, reason=payload.reason)


@router.post("/deactivate", response_model=KillSwitchStateResponse, status_code=status.HTTP_201_CREATED)
def deactivate_kill_switch(
    payload: KillSwitchToggleRequest,
    actor: str = Depends(_admin_actor),
    service: KillSwitchService = Depends(get_kill_switch_service),
) -> KillSwitchStateResponse:
    state = service.deactivate(actor, payload.reason)
    return KillSwitchStateResponse(state=state, actor=actor, reason=payload.reason)
