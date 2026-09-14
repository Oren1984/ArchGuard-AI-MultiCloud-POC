from __future__ import annotations

from app.domain.enums import CheckResult, RiskLevel
from app.governance.approval_gate import decide_routing


def test_failed_evaluation_always_blocks_even_if_ai_says_no_approval_needed():
    decision = decide_routing(
        RiskLevel.LOW, CheckResult.FAILED, ai_requires_approval=False, kill_switch_active=False
    )
    assert decision.blocked is True
    assert decision.requires_approval is False


def test_active_kill_switch_blocks_regardless_of_risk_or_result():
    decision = decide_routing(
        RiskLevel.LOW, CheckResult.PASSED, ai_requires_approval=False, kill_switch_active=True
    )
    assert decision.blocked is True
    assert "kill switch" in decision.block_reason.lower()


def test_high_risk_requires_approval_even_when_ai_did_not_flag_it():
    decision = decide_routing(
        RiskLevel.HIGH, CheckResult.PASSED, ai_requires_approval=False, kill_switch_active=False
    )
    assert decision.blocked is False
    assert decision.requires_approval is True


def test_critical_risk_requires_approval():
    decision = decide_routing(
        RiskLevel.CRITICAL, CheckResult.PASSED, ai_requires_approval=False, kill_switch_active=False
    )
    assert decision.requires_approval is True


def test_warning_result_requires_approval_even_at_low_risk():
    decision = decide_routing(
        RiskLevel.LOW, CheckResult.WARNING, ai_requires_approval=False, kill_switch_active=False
    )
    assert decision.blocked is False
    assert decision.requires_approval is True


def test_low_risk_passed_no_ai_flag_auto_clears():
    decision = decide_routing(
        RiskLevel.LOW, CheckResult.PASSED, ai_requires_approval=False, kill_switch_active=False
    )
    assert decision.blocked is False
    assert decision.requires_approval is False


def test_ai_requested_approval_is_honored_even_at_low_risk():
    decision = decide_routing(
        RiskLevel.LOW, CheckResult.PASSED, ai_requires_approval=True, kill_switch_active=False
    )
    assert decision.requires_approval is True
