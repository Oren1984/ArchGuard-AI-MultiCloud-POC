"""Domain enums shared across services, repositories, and the API layer.

These are pure Python enums with zero framework or cloud-provider
dependencies — the vendor-independence boundary starts here.
"""

from __future__ import annotations

import enum


class EventType(str, enum.Enum):
    DEPLOYMENT_FAILURE = "deployment_failure"
    SECURITY_ALERT = "security_alert"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    AVAILABILITY_OUTAGE = "availability_outage"
    DATA_INTEGRITY = "data_integrity"
    CONFIGURATION_DRIFT = "configuration_drift"
    COST_ANOMALY = "cost_anomaly"


class Environment(str, enum.Enum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"


class SeverityIndicator(str, enum.Enum):
    """Severity as reported by the source system — an input, not the computed risk."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventStatus(str, enum.Enum):
    OPEN = "open"
    RISK_ASSESSED = "risk_assessed"
    RECOMMENDATION_EVALUATED = "recommendation_evaluated"
    PENDING_APPROVAL = "pending_approval"
    BLOCKED = "blocked"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTION_SIMULATED = "action_simulated"


class ProposedActionType(str, enum.Enum):
    NOTIFY_ONLY = "notify_only"
    RESTART_SERVICE = "restart_service"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    SCALE_RESOURCES = "scale_resources"
    ISOLATE_COMPONENT = "isolate_component"
    ROTATE_CREDENTIALS = "rotate_credentials"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    NO_ACTION = "no_action"
    # Categorically dangerous — always blocked by the safety evaluator,
    # regardless of confidence or risk level. Never auto-executed.
    DELETE_RESOURCE = "delete_resource"
    DISABLE_SECURITY_CONTROL = "disable_security_control"


DANGEROUS_ACTIONS: frozenset[ProposedActionType] = frozenset(
    {ProposedActionType.DELETE_RESOURCE, ProposedActionType.DISABLE_SECURITY_CONTROL}
)


class AIProviderName(str, enum.Enum):
    MOCK = "mock"
    OPENAI_COMPATIBLE = "openai_compatible"


class RecommendationStatus(str, enum.Enum):
    PENDING_EVALUATION = "pending_evaluation"
    EVALUATED = "evaluated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    ERROR = "error"


class CheckResult(str, enum.Enum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


class ApprovalDecisionType(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class KillSwitchState(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class AuditAction(str, enum.Enum):
    EVENT_CREATED = "event_created"
    RISK_ASSESSED = "risk_assessed"
    AI_RECOMMENDATION_REQUESTED = "ai_recommendation_requested"
    AI_RECOMMENDATION_BLOCKED_KILL_SWITCH = "ai_recommendation_blocked_kill_switch"
    AI_PROVIDER_FAILURE = "ai_provider_failure"
    EVALUATION_COMPLETED = "evaluation_completed"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    ACTION_SIMULATED = "action_simulated"
    ACTION_BLOCKED_KILL_SWITCH = "action_blocked_kill_switch"
    KILL_SWITCH_ACTIVATED = "kill_switch_activated"
    KILL_SWITCH_DEACTIVATED = "kill_switch_deactivated"
    PROVIDER_REGRESSION_EVALUATED = "provider_regression_evaluated"


class RecommendationFinalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"
