"""Immutable value objects used by the deterministic risk engine and evaluators."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.enums import RiskLevel


@dataclass(frozen=True, slots=True)
class TriggeredRule:
    rule_id: str
    description: str
    points: int
    category: str


@dataclass(frozen=True, slots=True)
class RiskScore:
    score: int
    level: RiskLevel
    triggered_rules: tuple[TriggeredRule, ...] = field(default_factory=tuple)
    explanation: str = ""

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 100:
            raise ValueError(f"Risk score must be within [0, 100], got {self.score}")


@dataclass(frozen=True, slots=True)
class ConfidenceScore:
    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"Confidence must be within [0.0, 1.0], got {self.value}")
