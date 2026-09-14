"""Synthetic seed data loader.

Run inside the app container (or locally with DATABASE_URL pointed at the
compose Postgres): `python -m seed.seed_data`

Populates a small, representative set of events covering every terminal
workflow outcome (auto-cleared, approved, rejected, blocked-by-safety,
blocked-by-provider-failure) so the dashboard and API have something to
show immediately after `docker compose up`.
"""

from __future__ import annotations

import sys

from app.composition import build_services
from app.database.session import session_scope
from app.domain.enums import ApprovalDecisionType, Environment, EventType, SeverityIndicator

SEED_ACTOR = "system:seed"


def run() -> None:
    with session_scope() as db:
        services = build_services(db)

        print(
            f"Running regression evaluation for provider={services.provider.name} to establish eligibility..."
        )
        eligibility = services.regression_service.run(
            SEED_ACTOR,
            services.provider,
            services.settings.ai_model_name,
            services.settings.ai_prompt_version,
        )
        print(f"  -> eligible={eligibility.eligible} pass_rate={eligibility.pass_rate:.2f}")

        # 1) Low risk -> auto-cleared -> simulated action
        low = services.event_service.create_event(
            SEED_ACTOR,
            EventType.PERFORMANCE_DEGRADATION,
            source="datadog",
            description="Latency briefly exceeded threshold on the reporting worker; no user impact observed.",
            affected_service="reporting-worker",
            environment=Environment.DEVELOPMENT,
            severity=SeverityIndicator.LOW,
            evidence=["p99 latency 810ms for 2 minutes"],
        )
        services.risk_service.assess(SEED_ACTOR, low.id)
        services.ai_service.request_and_evaluate(SEED_ACTOR, low.id)
        print(f"Seeded LOW-risk event {low.id} -> auto-clear path")

        # 2) High risk -> pending approval -> approved -> simulated action
        high = services.event_service.create_event(
            SEED_ACTOR,
            EventType.AVAILABILITY_OUTAGE,
            source="pagerduty",
            description="Elevated 5xx error rate on the payments service following the latest deploy.",
            affected_service="payments",
            environment=Environment.PRODUCTION,
            severity=SeverityIndicator.HIGH,
            evidence=["error rate 12% over 5 minutes", "deploy correlation confirmed"],
        )
        services.risk_service.assess(SEED_ACTOR, high.id)
        high_rec = services.ai_service.request_and_evaluate(SEED_ACTOR, high.id)
        services.approval_service.decide(
            "approver:oncall-lead",
            high_rec.id,
            ApprovalDecisionType.APPROVED,
            "Rollback approved; matches runbook.",
        )
        print(f"Seeded HIGH-risk event {high.id} -> approved -> simulated action")

        # 3) Critical risk -> pending approval -> rejected
        critical = services.event_service.create_event(
            SEED_ACTOR,
            EventType.UNAUTHORIZED_ACCESS,
            source="siem",
            description="Anomalous admin-privilege escalation detected on the auth service from an unrecognized source.",
            affected_service="auth",
            environment=Environment.PRODUCTION,
            severity=SeverityIndicator.CRITICAL,
            evidence=["3 privilege escalations from unrecognized source IP"],
        )
        services.risk_service.assess(SEED_ACTOR, critical.id)
        critical_rec = services.ai_service.request_and_evaluate(SEED_ACTOR, critical.id)
        services.approval_service.decide(
            "approver:security-lead",
            critical_rec.id,
            ApprovalDecisionType.REJECTED,
            "Escalating to incident commander manually instead of automated path.",
        )
        print(f"Seeded CRITICAL-risk event {critical.id} -> rejected")

        # 4) Dangerous proposed action -> blocked by safety gate
        dangerous = services.event_service.create_event(
            SEED_ACTOR,
            EventType.DATA_INTEGRITY,
            source="synthetic-test",
            description="TRIGGER_DANGEROUS: corruption detected in the billing ledger table.",
            affected_service="billing",
            environment=Environment.PRODUCTION,
            severity=SeverityIndicator.CRITICAL,
            evidence=["checksum mismatch on ledger partition 7"],
        )
        services.risk_service.assess(SEED_ACTOR, dangerous.id)
        services.ai_service.request_and_evaluate(SEED_ACTOR, dangerous.id)
        print(f"Seeded event {dangerous.id} with a dangerous proposed action -> blocked by safety gate")

        # 5) Provider unavailable -> blocked, provider failure recorded
        unavailable = services.event_service.create_event(
            SEED_ACTOR,
            EventType.CONFIGURATION_DRIFT,
            source="synthetic-test",
            description="TRIGGER_UNAVAILABLE: configuration drift detected on the checkout-api deployment.",
            affected_service="checkout-api",
            environment=Environment.STAGING,
            severity=SeverityIndicator.MEDIUM,
            evidence=["3 config keys drifted from baseline"],
        )
        services.risk_service.assess(SEED_ACTOR, unavailable.id)
        try:
            services.ai_service.request_and_evaluate(SEED_ACTOR, unavailable.id)
        except Exception as exc:  # noqa: BLE001 — expected simulated provider failure
            print(f"Seeded event {unavailable.id} -> provider failure blocked as expected ({exc})")

        print("\nSeed complete.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
