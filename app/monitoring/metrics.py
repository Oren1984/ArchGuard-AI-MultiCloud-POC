"""Prometheus-compatible counters for the workflow (spec §11)."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, generate_latest

registry = CollectorRegistry()

events_created_total = Counter(
    "archguard_events_created_total", "Operational events created", registry=registry
)
risk_assessments_total = Counter(
    "archguard_risk_assessments_total", "Risk assessments computed", registry=registry
)
ai_evaluations_total = Counter(
    "archguard_ai_evaluations_total",
    "AI recommendation evaluations completed, by overall result",
    ["result"],
    registry=registry,
)
blocked_runs_total = Counter(
    "archguard_blocked_runs_total",
    "Runs blocked by evaluation, kill switch, or eligibility gates",
    ["reason"],
    registry=registry,
)
approvals_total = Counter(
    "archguard_approvals_total", "Human/system approval decisions, by outcome", ["outcome"], registry=registry
)
provider_failures_total = Counter(
    "archguard_provider_failures_total",
    "AI provider failures (unavailable/timeout/malformed)",
    registry=registry,
)


def render_latest() -> tuple[bytes, str]:
    return generate_latest(registry), CONTENT_TYPE_LATEST
