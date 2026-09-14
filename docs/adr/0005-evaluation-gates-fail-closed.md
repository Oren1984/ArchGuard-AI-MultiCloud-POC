# ADR 0005: Mandatory evaluation gates with fail-closed routing

## Status

Accepted

## Context

The spec mandates a specific flow — Input → Risk Assessment → AI/Mock Recommendation →
Automated Evaluation → Risk Classification → Human Approval at Defined Risk Points →
Simulated Next Stage or Blocked State — and states plainly: "No model or agent may advance
to the next workflow stage without documented evaluation results and explicit human
approval at defined risk points." It also requires an active kill switch to block AI
processing and simulated-action progression, and dangerous actions to always be blocked.

## Decision

Implement the routing decision as one pure function,
`app/governance/approval_gate.py::decide_routing()`, that has no database, AI-provider, or
cloud dependency and is directly unit-tested. `AIOrchestrationService` calls this function
only *after* running all five evaluation gates (schema, grounding, confidence, safety,
consistency) and checking the kill switch — never before. The function's rule ordering is
deliberately strict: kill-switch-active and evaluation-failed both hard-block regardless of
any other signal; high/critical risk or a WARNING evaluation result always force human
approval regardless of what the AI itself claims; only the remaining case (low/medium risk,
clean PASS, AI didn't ask for review) auto-clears — and even that path still writes a
system-attributed approval record, so there is no code path that reaches a simulated action
without an `ApprovalDecision` row existing.

## Consequences

- The state machine (`app/domain/workflow.py`) encodes exactly which transitions are legal,
  so "advance without evaluation" isn't just discouraged by convention — it's a Python
  exception (`InvalidStateTransitionError`) if attempted out of order.
- Because the routing decision is a pure function, its correctness is verifiable without
  spinning up a database or mocking an AI provider — see
  `tests/unit/test_approval_gate.py`'s exhaustive cases (kill switch, failed eval, high
  risk, warning result, low-risk auto-clear, AI-requested approval).
- The kill switch is checked twice in the AI-orchestration path (before calling the
  provider, and again immediately before simulating an approved action) specifically to
  close the race where the switch is activated between those two steps — a deliberate
  defense-in-depth choice, not redundancy for its own sake.
- Dangerous-action detection is categorical (not confidence-weighted) precisely because the
  spec requires it to always block — a probabilistic/confidence-based safety check would
  not satisfy "no AI recommendation may directly execute a real operational action" as an
  absolute guarantee.
