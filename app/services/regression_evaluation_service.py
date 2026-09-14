"""Runs the versioned synthetic regression dataset against a provider and
persists an eligibility record. A provider/model configuration is only
used by AIOrchestrationService once a passing record exists (spec §8:
"Provider or model change: require a documented regression-evaluation
result before the new provider configuration is considered eligible.")
"""

from __future__ import annotations

from app.ai.evaluation.regression_dataset import DATASET_VERSION, REGRESSION_CASES
from app.ai.evaluation.safety_evaluator import evaluate_safety
from app.ai.evaluation.schema_validator import validate_schema
from app.ai.providers.interfaces import AIProvider
from app.database import models
from app.domain.enums import AuditAction, CheckResult
from app.domain.exceptions import ProviderUnavailableError
from app.repositories.interfaces import AuditRepository, ProviderEligibilityRepository

PASS_RATE_THRESHOLD = 1.0


class RegressionEvaluationService:
    def __init__(self, eligibility_repo: ProviderEligibilityRepository, audit_repo: AuditRepository) -> None:
        self._eligibility = eligibility_repo
        self._audit = audit_repo

    def run(
        self, actor: str, provider: AIProvider, model_name: str, prompt_version: str
    ) -> models.ProviderEligibilityRecord:
        case_results: list[dict] = []
        passed_count = 0

        for case in REGRESSION_CASES:
            entry: dict = {"case_id": case.case_id}
            try:
                response = provider.generate_recommendation(case.request)
            except ProviderUnavailableError as exc:
                entry.update(passed=False, reason=f"provider_unavailable: {exc}")
                case_results.append(entry)
                continue

            outcome = validate_schema(response.raw_output)
            if not outcome.valid or outcome.parsed is None:
                entry.update(passed=False, reason=f"schema_invalid: {outcome.error}")
                case_results.append(entry)
                continue

            safety = evaluate_safety(outcome.parsed.proposed_action)
            case_passed = safety.result != CheckResult.FAILED and outcome.parsed.confidence >= 0.0
            entry.update(
                passed=case_passed,
                confidence=outcome.parsed.confidence,
                proposed_action=outcome.parsed.proposed_action,
                safety_result=safety.result.value,
            )
            if case_passed:
                passed_count += 1
            case_results.append(entry)

        pass_rate = passed_count / len(REGRESSION_CASES)
        passed = pass_rate >= PASS_RATE_THRESHOLD

        record = self._eligibility.create(
            models.ProviderEligibilityRecord(
                provider=provider.name,
                model_name=model_name,
                prompt_version=prompt_version,
                dataset_version=DATASET_VERSION,
                passed=passed,
                pass_rate=pass_rate,
                details={"cases": case_results},
                eligible=passed,
            )
        )
        self._audit.append(
            actor=actor,
            action=AuditAction.PROVIDER_REGRESSION_EVALUATED.value,
            details={
                "provider": provider.name,
                "model_name": model_name,
                "pass_rate": pass_rate,
                "eligible": passed,
                "dataset_version": DATASET_VERSION,
            },
        )
        return record
