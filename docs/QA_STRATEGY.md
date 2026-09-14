# QA Strategy

## Test levels

| Level | Directory | What it covers | DB required |
| --- | --- | --- | --- |
| Unit | `tests/unit/` | Risk engine scoring/levels/explanations, workflow state machine, approval-routing policy, all five evaluation gates in isolation, mock-provider determinism and test-trigger hooks, kill-switch service (in-memory fakes), identity/authz regex rules, log redaction, DB-unavailable handling | No |
| Repository/DB | `tests/integration/` | PostgreSQL persistence, `CHECK` constraints, `ON DELETE CASCADE`, hash-chain integrity/tamper detection, transaction rollback (savepoint), Alembic upgrade/downgrade against a disposable database | Yes (real PostgreSQL) |
| API | `tests/api/` | Every endpoint: event CRUD, risk-assessment workflow, AI recommendation + evaluation retrieval, approval/rejection, invalid state transitions, health/readiness, request validation, provider eligibility | Yes |
| AI assurance | `tests/api/test_ai_assurance_api.py` | Valid response, malformed response, provider unavailable, ungrounded, low-confidence (hard floor and warning-tier), dangerous action, regression-evaluation gating, AI-outage fallback | Yes |
| Security | `tests/security/` | Oversized input, injection-shaped payloads, actor-header format enforcement, unauthorized/invalid approval attempts, dangerous-action blocking, secret redaction | Yes |
| E2E | `tests/e2e/` | The full spec-mandated scenario end to end via the API, plus the same scenario with the kill switch active | Yes |

## Test environments

- **Unit tests** run with zero external dependencies — no Docker, no network — so they're
  the fast inner loop and also what CI runs first.
- **DB-backed tests** connect to `TEST_DATABASE_URL` (default: `archguard_test` on
  localhost:5432), created automatically the first time the Compose Postgres volume
  initializes (`scripts/init-test-db.sql`) or by the CI Postgres service container. They
  **skip cleanly with a clear message** rather than fail when Postgres isn't reachable, so
  the suite is still runnable on a machine without Docker.
- Each DB-backed test runs inside its own transaction (`tests/conftest.py::db_session`),
  rolled back on teardown — full isolation between tests, no manual cleanup, and no test
  ever touches the primary `archguard` demo database.
- The Alembic migration tests are further isolated onto their own disposable database
  (`archguard_migrations_test`, created/dropped per test) so migration up/down never
  interferes with the shared schema the other DB-backed tests rely on.

## PostgreSQL strategy

SQLite is never used as a stand-in for PostgreSQL-backed tests — this project relies on
PostgreSQL-specific behavior (`JSONB`, `Identity()` for the audit sequence, `CHECK`
constraints, `ON DELETE CASCADE`) that SQLite doesn't faithfully emulate. Unit tests avoid
the database entirely by testing pure domain/governance logic and using lightweight
in-memory fakes for repository Protocols (see `tests/unit/test_kill_switch.py`) rather than
mocking SQLAlchemy.

## Security validation

Covers: request-size/format validation (oversized description/evidence/source, wrong
types, unknown fields), SQL-injection-shaped and script-tag-shaped payloads (proven inert
because all persistence goes through parameterized SQLAlchemy queries and API responses
are JSON, not rendered HTML), actor-identity format enforcement, role-based approval
authorization (only `approver:`/`admin:`-prefixed identities may approve/reject), and
verification that unhandled errors return only a generic message + correlation ID — never
exception internals, stack traces, or credential fragments. `.env.example` is checked for
the absence of anything resembling a real credential.

## E2E scope

One full scenario (`tests/e2e/test_full_workflow.py`) drives the entire mandated flow
through the real HTTP API: create event → deterministic risk → AI recommendation →
evaluation → route to human approval (high risk) → approve → verify every transition
appears in the hash-chained audit trail → verify final state via both the API and the
rendered dashboard HTML. A second scenario repeats the same flow with the kill switch
active and asserts it fails closed at the AI-recommendation step, confirms the event lands
in `blocked`, and confirms the block is itself audited.

## Test evidence

Exact pass/fail counts and the commands used to produce them are recorded in the project's
final verification report (see the repository's completion report / `SESSION_HANDOFF.md`
in the workspace root for this session's run). Reproduce locally with:

```bash
pytest tests/unit -q
pytest tests/integration tests/api tests/security tests/e2e -q
```

## Known gaps

- No load/performance testing — out of scope for a POC demonstrating workflow correctness.
- No browser-driven UI test of the dashboard (it's server-rendered and read-only; covered
  indirectly by asserting on rendered HTML content in `tests/e2e/test_full_workflow.py`).
- The OpenAI-compatible provider has no live-integration test (would require real
  credentials, which this POC deliberately does not require or ship).
- Consistency-check coverage is necessarily limited to the mock provider's deterministic
  behavior plus one synthetic drifting-provider unit test
  (`tests/unit/test_evaluation_gates.py::test_consistency_warns_when_repeat_calls_diverge`);
  a real non-deterministic LLM's actual drift characteristics aren't exercised.
- Migration tests cover upgrade/downgrade correctness on a disposable database, not
  migration behavior against a large pre-existing dataset.
