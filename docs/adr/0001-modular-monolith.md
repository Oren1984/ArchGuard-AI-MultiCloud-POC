# ADR 0001: Modular monolith over microservices

## Status

Accepted

## Context

The spec requires demonstrating pragmatic OOP, clear separation of concerns (API,
domain, services, AI, repositories, governance, monitoring), and vendor-independence for
AI providers and persistence — while explicitly forbidding unnecessary architectural
complexity: "Do not introduce microservices, Kubernetes, event streaming, unnecessary
abstractions, excessive design patterns, or administrative overhead unless they are
essential to the agreed acceptance criteria."

## Decision

Build one deployable FastAPI process (`app/main.py`) internally organized into strictly
layered packages (`api` → `services` → `domain`/`repositories`/`ai`/`governance`), with the
replacement seams that actually matter (AI provider, persistence) expressed as
`typing.Protocol` interfaces rather than as network boundaries between services.

## Consequences

- One process to build, test, deploy, and reason about — no inter-service network calls,
  no distributed-transaction concerns, no service-discovery/orchestration machinery.
- The audit trail and evaluation gates can be enforced in a single transaction per
  workflow step, which would require distributed-transaction handling or eventual
  consistency if this were split across services.
- Vendor independence (AI provider, persistence) is achieved via in-process Protocols
  instead of service boundaries — proven sufficient by `app/composition.py` and
  `app/api/dependencies.py` both wiring the same Protocol-typed services from different
  concrete implementations.
- If this POC ever needed independent scaling of, say, AI evaluation vs. the API layer,
  that would require revisiting this decision — not attempted here, as it's not required
  by the current acceptance criteria.
