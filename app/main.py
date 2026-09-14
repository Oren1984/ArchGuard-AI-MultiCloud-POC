"""FastAPI application entry point — composition root for the API layer."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.error_handlers import register_error_handlers
from app.api.middleware import CorrelationIdMiddleware
from app.api.routers import audit, events, kill_switch, providers, recommendations, system
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.dashboard.router import router as dashboard_router

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="ArchGuard AI MultiCloud POC",
    description=(
        "Locally runnable POC demonstrating explainable deterministic risk assessment, "
        "human-controlled AI workflow, evaluation gates, and vendor-independent architecture."
    ),
    version="0.1.0",
)

app.add_middleware(CorrelationIdMiddleware, header_name=settings.correlation_id_header)
register_error_handlers(app)

app.include_router(events.router)
app.include_router(recommendations.router)
app.include_router(audit.router)
app.include_router(kill_switch.router)
app.include_router(providers.router)
app.include_router(system.router)
app.include_router(dashboard_router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard")
