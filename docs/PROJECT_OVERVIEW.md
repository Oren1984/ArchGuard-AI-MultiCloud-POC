# Project Overview

**ArchGuard AI MultiCloud POC** is a locally runnable proof-of-concept that shows one way to
let an AI assistant help with operational incidents without letting it act on its own. Each
incident gets an explainable rule-based risk score. The AI's recommendation then has to pass
automated checks, a human approves it where the risk calls for that, and every step is
written to a tamper-evident audit log. Actions are only ever simulated.

Portfolio category: **System Design & Architecture**. The project is mainly about how the
system is structured: layering, replaceable components, fail-closed control flow, and
auditability. It is a POC, not a production platform.

## The problem

Operations teams want help triaging incidents, and language models can suggest a plausible
response quickly. But "the model said so" is not an acceptable reason to roll back a
production deployment. A reviewer needs to know why an event was rated as risky, whether the
recommendation is grounded in the event's actual evidence, whether it proposes something
dangerous, who approved it, and whether the record of all this can be trusted.

This project explores a design that answers those questions by construction instead of by
policy documents.

## Intended users

- **Engineers and architects** evaluating patterns for human-in-the-loop AI in operations.
- **Reviewers** (security, compliance, platform) who want to see what an auditable AI
  decision trail can look like.
- **Portfolio readers** looking for a worked example of system design decisions and their
  tradeoffs.

It is not intended for real incident handling. The identity model is a demo convention, the
AI provider is a deterministic mock by default, and actions are simulated.

## Purpose and practical value

- Shows how to keep a **deterministic, explainable risk engine** as the authority on risk,
  separate from the AI component.
- Shows how to treat AI output as **untrusted input** that must pass schema, grounding,
  confidence, safety, and consistency checks before anyone sees it as a recommendation.
- Shows **fail-closed routing**: a failed check, an active kill switch, or an unavailable
  provider blocks the workflow rather than letting it continue.
- Shows **provider independence**: the AI provider sits behind one interface, and a provider
  or model must pass a regression evaluation before the system will use it.
- Provides a **runnable reference** (Docker Compose, PostgreSQL, 129 automated tests) rather
  than a diagram-only design.

## Implemented capabilities

| Capability | Status |
| --- | --- |
| REST API for events, risk assessment, recommendations, evaluation, approval, audit, kill switch, provider eligibility | Implemented, exercised by tests and the demo |
| Deterministic risk engine (9 weighted rules, score 0–100, four levels, human-readable explanation) | Implemented |
| Explicit event state machine with terminal states | Implemented |
| Five evaluation gates on AI output (schema, grounding, confidence, safety, consistency) | Implemented |
| Approval routing with role-prefix authorization (`approver:` / `admin:`) | Implemented (demo identity model, not real authentication) |
| Database-backed kill switch that blocks AI calls and simulated actions | Implemented |
| Hash-chained audit log with a verification endpoint | Implemented |
| Provider regression evaluation (versioned synthetic dataset, 100% pass required) | Implemented |
| Read-only server-rendered dashboard | Implemented |
| Health, readiness, and Prometheus-format metrics | Implemented |
| Deterministic mock AI provider with failure-trigger keywords | Implemented, the default |
| OpenAI-compatible HTTP provider | Code exists; optional, needs external credentials, not exercised by tests or the demo |
| AWS and GCP Terraform reference designs | Static validation only; never planned or applied |
| Real execution of remediation actions | Not implemented by design; actions are simulated |

## Main workflow

1. An operator submits an operational event (type, environment, severity, affected service,
   description, evidence).
2. The risk engine scores it deterministically and records which rules fired.
3. The AI provider is asked for a recommendation. This only happens if the kill switch is off
   and the provider/model has a passing regression-evaluation record.
4. The output is validated and evaluated by the five gates.
5. The approval gate decides: **block** (any failed gate or active kill switch), **require
   human approval** (high/critical risk, any warning, or the AI asks for it), or
   **auto-clear** (low/medium risk with all checks passed).
6. An approver approves or rejects. Approval leads to a simulated action. If the kill switch
   was activated in the meantime, the event is blocked.
7. Every completed step is appended to the audit log. One exception, error responses whose
   writes are rolled back, is described in
   [GOVERNANCE_AND_VALIDATION.md](GOVERNANCE_AND_VALIDATION.md#known-limitations).

The full state diagram is in [ARCHITECTURE.md](ARCHITECTURE.md#workflow-and-routing).

## Scope boundaries

In scope:

- Single-process application, PostgreSQL persistence, local Docker Compose runtime.
- Synthetic events and seed data only.
- Static infrastructure-as-code reference for two clouds.

Out of scope, and not claimed:

- Real authentication or authorization (the actor header is self-declared).
- Real AI model quality. The default mock is deterministic so the checks themselves can be
  tested.
- Executing real operational actions, calling cloud APIs, or integrating with paging or
  ticketing systems. The `source` field (for example `pagerduty`) is a free-text label, not
  an integration.
- Any cloud deployment. The Terraform has never been applied.
- Production hardening (high availability, private networking, secret rotation, rate
  limiting).

## Concrete example

This is the run performed while preparing this documentation, using the steps in
[DEMO_AND_OPERATIONS.md](DEMO_AND_OPERATIONS.md#demo-walkthrough).

An operator (`operator:demo`) reports an availability outage: elevated 5xx errors on the
`payments` service in `production`, severity `high`, with the evidence `error rate 12%`.

- **Risk assessment:** score **70/100 → HIGH**. Four rules fired: production environment
  (+25), high severity (+15), availability outage (+15), and critical service (+15).
- **AI recommendation (mock provider):** `rollback_deployment` with confidence 0.656, citing
  the submitted evidence.
- **Evaluation:** schema valid; grounding, confidence, safety, and consistency all
  **passed**. Because the risk is HIGH, routing is **PENDING_APPROVAL**.
- **Authorization:** the same approval request sent as `operator:demo` returned **HTTP 403**.
- **Approval:** `approver:jane` approved it, and the event moved to **ACTION_SIMULATED**.
  Nothing outside the database changed.
- **Audit trail:** six entries (`event_created`, `risk_assessed`,
  `ai_recommendation_requested`, `evaluation_completed`, `approval_granted`,
  `action_simulated`), and `GET /audit/verify` returned `{"chain_intact": true}`.

The seeded data shows the other outcomes, including a recommendation blocked by the safety
gate because it proposed `delete_resource`:

![Dashboard detail for a seeded event blocked by the safety gate](images/dashboard-event-blocked-by-safety-gate.png)
