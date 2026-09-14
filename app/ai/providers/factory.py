"""Builds the configured AI provider. The only place that branches on
AI_PROVIDER — everything else depends on the AIProvider Protocol."""

from __future__ import annotations

from app.ai.providers.interfaces import AIProvider
from app.ai.providers.mock_provider import MockAIProvider
from app.ai.providers.openai_compatible_provider import OpenAICompatibleProvider
from app.core.config import Settings
from app.domain.enums import AIProviderName


def build_provider(settings: Settings) -> AIProvider:
    if settings.ai_provider == AIProviderName.OPENAI_COMPATIBLE.value:
        return OpenAICompatibleProvider(
            base_url=settings.openai_compatible_base_url,
            api_key=settings.openai_compatible_api_key,
            model=settings.openai_compatible_model,
        )
    return MockAIProvider()
