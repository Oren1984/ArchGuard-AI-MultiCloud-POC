# ADR 0003: Replaceable AI provider behind a Protocol, deterministic mock by default

## Status

Accepted

## Context

The spec requires a replaceable AI provider abstraction, a deterministic local mock that
needs no external credentials as the default, and optional support for one OpenAI-compatible
provider — with the whole project required to fully pass without the latter.

## Decision

Define one `AIProvider` Protocol (`app/ai/providers/interfaces.py`) with a single method,
`generate_recommendation(request) -> ProviderResponse`, where `ProviderResponse.raw_output`
is treated as **untrusted** by everything downstream until it passes the schema-validation
gate. Implement `MockAIProvider` as a pure function of its input (hash-seeded jitter, not
real randomness), so identical requests produce identical output — this is what makes the
consistency-check evaluation gate meaningful without needing a real non-deterministic LLM
in tests. Implement `OpenAICompatibleProvider` against the same Protocol, selected via
`AI_PROVIDER=openai_compatible`, but not required for any test or demo path to pass.

## Consequences

- Swapping providers requires zero changes to `app/services`, `app/ai/evaluation`, or
  `app/governance` — only `app/ai/providers/factory.py::build_provider()` branches on
  configuration.
- The mock provider's determinism is a deliberate testability feature, not a limitation
  masked as one — it's documented as such in `app/ai/providers/mock_provider.py`'s module
  docstring.
- Mock-provider test-trigger keywords (`TRIGGER_MALFORMED`, `TRIGGER_UNAVAILABLE`, etc.,
  embedded in the event description) give deterministic, reproducible coverage of every
  AI-assurance failure path without a mocking framework — a pragmatic trade-off that
  couples test scenarios to a magic-string convention, judged acceptable for a POC's scope.
- A provider/model change is gated by a regression-evaluation requirement (ADR 0005 /
  `docs/AI_ASSURANCE.md`) regardless of which provider is configured, so this Protocol
  doesn't become a way to bypass evaluation discipline.
