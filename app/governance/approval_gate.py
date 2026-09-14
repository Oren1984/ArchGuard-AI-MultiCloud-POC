"""Pure approval-routing policy. No DB, no AI provider, no cloud dependency
— exercised directly by unit tests (spec §14 "Approval-state transitions").

Enforces: a failed evaluation always blocks; an active kill switch always
blocks; high/critical risk always requires human approval; a WARNING-level
evaluation (e.g. low confidence) always requires human approval.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import CheckResult, RiskLevel

HIGH_RISK_LEVELS = frozenset({RiskLevel.HIGH, RiskLevel.CRITICAL})


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    requires_approval: bool
    blocked: bool
    block_reason: str | None


def decide_routing(
    risk_level: RiskLevel,
    overall_result: CheckResult,
    ai_requires_approval: bool,
    kill_switch_active: bool,
) -> RoutingDecision:
    if kill_switch_active:
        return RoutingDecision(requires_approval=False, blocked=True, block_reason="Kill switch is active.")

    if overall_result == CheckResult.FAILED:
        return RoutingDecision(
            requires_approval=False, blocked=True, block_reason="Automated evaluation failed."
        )

    requires_approval = (
        ai_requires_approval or risk_level in HIGH_RISK_LEVELS or overall_result == CheckResult.WARNING
    )
    return RoutingDecision(requires_approval=requires_approval, blocked=False, block_reason=None)
