"""Domain-level exceptions. Framework-independent; the API layer maps these
to HTTP status codes (see app/api/error_handlers.py)."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain errors."""


class EntityNotFoundError(DomainError):
    def __init__(self, entity: str, entity_id: object) -> None:
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(f"{entity} not found: {entity_id}")


class InvalidStateTransitionError(DomainError):
    def __init__(self, current: str, attempted: str) -> None:
        self.current = current
        self.attempted = attempted
        super().__init__(f"Cannot transition from '{current}' to '{attempted}'")


class KillSwitchActiveError(DomainError):
    def __init__(self, stage: str) -> None:
        self.stage = stage
        super().__init__(f"Kill switch is active — blocked at stage: {stage}")


class EvaluationGateFailedError(DomainError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Evaluation gate failed: {reason}")


class ProviderUnavailableError(DomainError):
    def __init__(self, provider: str, detail: str = "") -> None:
        self.provider = provider
        super().__init__(f"AI provider '{provider}' is unavailable. {detail}".strip())


class MalformedProviderResponseError(DomainError):
    def __init__(self, provider: str, detail: str = "") -> None:
        self.provider = provider
        super().__init__(f"AI provider '{provider}' returned a malformed response. {detail}".strip())


class ProviderNotEligibleError(DomainError):
    def __init__(self, provider: str, model: str) -> None:
        self.provider = provider
        self.model = model
        super().__init__(
            f"Provider '{provider}' model '{model}' has no passing regression-evaluation "
            "record. Run POST /providers/regression-evaluation before use."
        )


class UnauthorizedActionError(DomainError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
