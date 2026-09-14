from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_audit_repo
from app.api.schemas import AuditLogResponse
from app.repositories.postgres_repositories import SqlAlchemyAuditRepository

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=list[AuditLogResponse])
def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    audit_repo: SqlAlchemyAuditRepository = Depends(get_audit_repo),
) -> list[AuditLogResponse]:
    return [AuditLogResponse.model_validate(e) for e in audit_repo.list_all(limit, offset)]


@router.get("/events/{event_id}/audit", response_model=list[AuditLogResponse])
def list_event_audit_logs(
    event_id: uuid.UUID, audit_repo: SqlAlchemyAuditRepository = Depends(get_audit_repo)
) -> list[AuditLogResponse]:
    return [AuditLogResponse.model_validate(e) for e in audit_repo.list_for_event(event_id)]


@router.get("/audit/verify")
def verify_audit_chain(audit_repo: SqlAlchemyAuditRepository = Depends(get_audit_repo)) -> dict:
    return {"chain_intact": audit_repo.verify_chain()}
