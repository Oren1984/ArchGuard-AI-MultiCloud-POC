from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.monitoring.health import check_readiness
from app.monitoring.metrics import render_latest

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(response: Response) -> dict:
    readiness = check_readiness()
    response.status_code = status.HTTP_200_OK if readiness.ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return {"ready": readiness.ready, "database_available": readiness.database_available}


@router.get("/metrics")
def metrics() -> Response:
    payload, content_type = render_latest()
    return Response(content=payload, media_type=content_type)
