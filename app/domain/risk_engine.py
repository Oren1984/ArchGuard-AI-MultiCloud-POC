"""Deterministic, explainable risk-scoring engine.

Pure function of its inputs: identical RiskInput -> identical RiskScore,
every time. No AI provider, database, or cloud dependency, so the engine
keeps working even when the AI provider is unavailable (see spec §6.3).

Rules are plain Python objects rather than a rule-management platform —
enough to be configurable and unit-testable without over-building.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.domain.enums import Environment, EventType, RiskLevel, SeverityIndicator
from app.domain.value_objects import RiskScore, TriggeredRule

CRITICAL_SERVICES: frozenset[str] = frozenset(
    {"payments", "auth", "authentication", "database", "billing", "identity"}
)

DANGER_KEYWORDS: frozenset[str] = frozenset(
    {"credential", "delete", "customer data", "production data", "exfiltrat", "breach"}
)


@dataclass(frozen=True, slots=True)
class RiskInput:
    event_type: EventType
    environment: Environment
    severity: SeverityIndicator
    affected_service: str
    description: str
    evidence_count: int


@dataclass(frozen=True, slots=True)
class RiskRule:
    rule_id: str
    description: str
    category: str
    points: int
    predicate: Callable[[RiskInput], bool]


def _rule_prod_env(i: RiskInput) -> bool:
    return i.environment == Environment.PRODUCTION


def _rule_severity_critical(i: RiskInput) -> bool:
    return i.severity == SeverityIndicator.CRITICAL


def _rule_severity_high(i: RiskInput) -> bool:
    return i.severity == SeverityIndicator.HIGH


def _rule_security_type(i: RiskInput) -> bool:
    return i.event_type in {EventType.SECURITY_ALERT, EventType.UNAUTHORIZED_ACCESS}


def _rule_data_integrity_type(i: RiskInput) -> bool:
    return i.event_type == EventType.DATA_INTEGRITY


def _rule_availability_type(i: RiskInput) -> bool:
    return i.event_type == EventType.AVAILABILITY_OUTAGE


def _rule_no_evidence(i: RiskInput) -> bool:
    return i.evidence_count == 0


def _rule_critical_service(i: RiskInput) -> bool:
    return i.affected_service.strip().lower() in CRITICAL_SERVICES


def _rule_danger_keywords(i: RiskInput) -> bool:
    text = i.description.lower()
    return any(keyword in text for keyword in DANGER_KEYWORDS)


DEFAULT_RULES: tuple[RiskRule, ...] = (
    RiskRule(
        "R-ENV-PROD", "Production environment increases blast radius", "environment", 25, _rule_prod_env
    ),
    RiskRule(
        "R-SEV-CRITICAL", "Source-reported severity is critical", "severity", 30, _rule_severity_critical
    ),
    RiskRule("R-SEV-HIGH", "Source-reported severity is high", "severity", 15, _rule_severity_high),
    RiskRule(
        "R-TYPE-SECURITY",
        "Security/unauthorized-access event types carry elevated inherent risk",
        "event_type",
        20,
        _rule_security_type,
    ),
    RiskRule(
        "R-TYPE-DATA",
        "Data-integrity events risk irreversible corruption",
        "event_type",
        20,
        _rule_data_integrity_type,
    ),
    RiskRule(
        "R-TYPE-AVAILABILITY",
        "Availability outages affect active users",
        "event_type",
        15,
        _rule_availability_type,
    ),
    RiskRule(
        "R-EVIDENCE-LOW", "No supporting evidence increases uncertainty", "evidence", 10, _rule_no_evidence
    ),
    RiskRule(
        "R-SERVICE-CRITICAL",
        "Affected service is on the critical-services list",
        "service",
        15,
        _rule_critical_service,
    ),
    RiskRule(
        "R-KEYWORD-DANGER",
        "Description contains high-sensitivity keywords",
        "content",
        10,
        _rule_danger_keywords,
    ),
)

_THRESHOLDS: tuple[tuple[int, RiskLevel], ...] = (
    (75, RiskLevel.CRITICAL),
    (50, RiskLevel.HIGH),
    (25, RiskLevel.MEDIUM),
    (0, RiskLevel.LOW),
)


def _level_for_score(score: int) -> RiskLevel:
    for floor, level in _THRESHOLDS:
        if score >= floor:
            return level
    return RiskLevel.LOW


class RiskEngine:
    """Stateless, deterministic. Safe to reuse a single instance app-wide."""

    def __init__(self, rules: tuple[RiskRule, ...] = DEFAULT_RULES) -> None:
        self._rules = rules

    @property
    def engine_version(self) -> str:
        return "risk-engine-v1"

    def assess(self, risk_input: RiskInput) -> RiskScore:
        triggered: list[TriggeredRule] = []
        total = 0
        for rule in self._rules:
            if rule.predicate(risk_input):
                total += rule.points
                triggered.append(TriggeredRule(rule.rule_id, rule.description, rule.points, rule.category))
        capped = min(total, 100)
        level = _level_for_score(capped)
        explanation = self._explain(risk_input, triggered, capped, level)
        return RiskScore(score=capped, level=level, triggered_rules=tuple(triggered), explanation=explanation)

    @staticmethod
    def _explain(risk_input: RiskInput, triggered: list[TriggeredRule], score: int, level: RiskLevel) -> str:
        if not triggered:
            return (
                f"No risk rules triggered for this {risk_input.event_type.value} event in "
                f"{risk_input.environment.value}. Score {score}/100 -> {level.value.upper()}."
            )
        reasons = "; ".join(f"{t.rule_id} (+{t.points}): {t.description}" for t in triggered)
        return f"Score {score}/100 -> {level.value.upper()}. Triggered rules: {reasons}."
