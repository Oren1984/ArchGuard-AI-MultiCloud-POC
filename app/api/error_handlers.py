"""Maps domain exceptions to structured HTTP error responses.

Never leaks internal exception details for unhandled errors — only the
correlation ID is returned, matching the "no secret/internal leakage in
responses" requirement (spec §14 Security Tests).
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import correlation_id_var, get_logger
from app.domain.exceptions import (
    DomainError,
    EntityNotFoundError,
    EvaluationGateFailedError,
    InvalidStateTransitionError,
    KillSwitchActiveError,
    MalformedProviderResponseError,
    ProviderNotEligibleError,
    ProviderUnavailableError,
    UnauthorizedActionError,
)

logger = get_logger(__name__)

_STATUS_MAP: tuple[tuple[type[DomainError], int], ...] = (
    (EntityNotFoundError, status.HTTP_404_NOT_FOUND),
    (UnauthorizedActionError, status.HTTP_403_FORBIDDEN),
    (KillSwitchActiveError, status.HTTP_423_LOCKED),
    (ProviderNotEligibleError, status.HTTP_409_CONFLICT),
    (InvalidStateTransitionError, status.HTTP_409_CONFLICT),
    (EvaluationGateFailedError, status.HTTP_422_UNPROCESSABLE_ENTITY),
    (ProviderUnavailableError, status.HTTP_502_BAD_GATEWAY),
    (MalformedProviderResponseError, status.HTTP_502_BAD_GATEWAY),
)


def _error_body(error: str, detail: str) -> dict:
    return {"error": error, "detail": detail, "correlation_id": correlation_id_var.get()}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body("validation_error", "Request payload failed validation."),
        )

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        http_status = status.HTTP_400_BAD_REQUEST
        for exc_type, mapped_status in _STATUS_MAP:
            if isinstance(exc, exc_type):
                http_status = mapped_status
                break
        return JSONResponse(status_code=http_status, content=_error_body(type(exc).__name__, str(exc)))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception processing request", extra={"path": str(request.url)})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("internal_error", "An unexpected error occurred."),
        )
