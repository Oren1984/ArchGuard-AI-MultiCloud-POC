from __future__ import annotations

from app.domain.enums import Environment, EventType, RiskLevel, SeverityIndicator
from app.domain.risk_engine import RiskEngine, RiskInput


def _input(**overrides) -> RiskInput:
    defaults = dict(
        event_type=EventType.PERFORMANCE_DEGRADATION,
        environment=Environment.DEVELOPMENT,
        severity=SeverityIndicator.LOW,
        affected_service="reporting-worker",
        description="Minor latency blip.",
        evidence_count=1,
    )
    defaults.update(overrides)
    return RiskInput(**defaults)


def test_low_risk_scores_low_with_no_triggered_rules():
    engine = RiskEngine()
    result = engine.assess(_input())
    assert result.level == RiskLevel.LOW
    assert result.triggered_rules == ()
    assert "no risk rules triggered" in result.explanation.lower()


def test_production_environment_adds_expected_points():
    engine = RiskEngine()
    dev_result = engine.assess(_input(environment=Environment.DEVELOPMENT))
    prod_result = engine.assess(_input(environment=Environment.PRODUCTION))
    assert prod_result.score == dev_result.score + 25
    assert any(r.rule_id == "R-ENV-PROD" for r in prod_result.triggered_rules)


def test_critical_severity_plus_production_plus_security_type_reaches_critical():
    engine = RiskEngine()
    result = engine.assess(
        _input(
            event_type=EventType.UNAUTHORIZED_ACCESS,
            environment=Environment.PRODUCTION,
            severity=SeverityIndicator.CRITICAL,
            affected_service="auth",
            evidence_count=0,
        )
    )
    # 25 (prod) + 30 (critical) + 20 (security type) + 10 (no evidence) + 15 (critical service) = 100
    assert result.score == 100
    assert result.level == RiskLevel.CRITICAL
    triggered_ids = {r.rule_id for r in result.triggered_rules}
    assert {
        "R-ENV-PROD",
        "R-SEV-CRITICAL",
        "R-TYPE-SECURITY",
        "R-EVIDENCE-LOW",
        "R-SERVICE-CRITICAL",
    } == triggered_ids


def test_score_is_capped_at_100():
    engine = RiskEngine()
    result = engine.assess(
        _input(
            event_type=EventType.DATA_INTEGRITY,
            environment=Environment.PRODUCTION,
            severity=SeverityIndicator.CRITICAL,
            affected_service="database",
            description="customer data breach involving stolen credentials",
            evidence_count=0,
        )
    )
    assert result.score == 100
    assert result.level == RiskLevel.CRITICAL


def test_identical_input_produces_identical_output():
    engine = RiskEngine()
    a = engine.assess(_input(environment=Environment.PRODUCTION))
    b = engine.assess(_input(environment=Environment.PRODUCTION))
    assert a.score == b.score
    assert a.level == b.level
    assert a.triggered_rules == b.triggered_rules


def test_explanation_lists_each_triggered_rule():
    engine = RiskEngine()
    result = engine.assess(_input(environment=Environment.PRODUCTION, severity=SeverityIndicator.HIGH))
    assert "R-ENV-PROD" in result.explanation
    assert "R-SEV-HIGH" in result.explanation


def test_critical_service_keyword_case_insensitive():
    engine = RiskEngine()
    result = engine.assess(_input(affected_service="  AUTH  "))
    assert any(r.rule_id == "R-SERVICE-CRITICAL" for r in result.triggered_rules)


def test_danger_keyword_in_description_triggers_rule():
    engine = RiskEngine()
    result = engine.assess(_input(description="Operator may need to delete stale records."))
    assert any(r.rule_id == "R-KEYWORD-DANGER" for r in result.triggered_rules)
