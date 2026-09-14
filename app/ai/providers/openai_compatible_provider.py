"""Optional OpenAI-compatible provider (chat-completions style HTTP API).

Disabled by default — the POC must fully pass with AI_PROVIDER=mock and no
credentials. Enabling this provider requires OPENAI_COMPATIBLE_BASE_URL,
OPENAI_COMPATIBLE_API_KEY, and OPENAI_COMPATIBLE_MODEL, and a passing
regression-evaluation record before the AI orchestration service will use it
(see app/services/regression_evaluation_service.py).
"""

from __future__ import annotations

import json

import httpx

from app.ai.providers.interfaces import ProviderResponse, RecommendationRequest
from app.domain.exceptions import MalformedProviderResponseError, ProviderUnavailableError

_SYSTEM_PROMPT = (
    "You are an operational incident assistant. Respond with a single JSON object "
    "containing exactly these keys: summary, suggested_response, evidence_references "
    "(array of strings), confidence (0.0-1.0), proposed_action, risk_notes, "
    "requires_human_approval (boolean). Do not include any text outside the JSON object."
)


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, model: str, timeout_seconds: float = 15.0) -> None:
        if not base_url or not api_key or not model:
            raise ProviderUnavailableError(self.name, "Missing base URL, API key, or model configuration.")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    def generate_recommendation(self, request: RecommendationRequest) -> ProviderResponse:
        user_prompt = (
            f"Event type: {request.event_type}\nEnvironment: {request.environment}\n"
            f"Severity: {request.severity}\nAffected service: {request.affected_service}\n"
            f"Description: {request.description}\nEvidence: {list(request.evidence)}\n"
            f"Deterministic risk score: {request.risk_score} ({request.risk_level})"
        )
        try:
            resp = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0,
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(self.name, str(exc)) from exc

        try:
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            raw_output = json.loads(content)
        except (KeyError, IndexError, ValueError) as exc:
            raise MalformedProviderResponseError(self.name, str(exc)) from exc

        return ProviderResponse(raw_output=raw_output, model_name=self._model, model_version=None)
