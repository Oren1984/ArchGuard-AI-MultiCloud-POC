# ArchGuard AI MultiCloud POC

A locally runnable, modular proof-of-concept for **human-controlled, evaluation-gated AI
decision support in operational incident response**. It demonstrates how to pair a
deterministic, explainable risk engine with a replaceable AI provider, force every AI
output through automated evaluation gates, and require human approval at defined risk
points — all fully auditable, all provider-independent, all runnable offline with no
cloud credentials.

## Business problem

Operations teams increasingly want AI assistance triaging incidents, but "the AI told me
to do it" is not an acceptable audit trail for a production action. This POC shows a
pattern for AI-assisted operations that a security/compliance reviewer can actually sign
off on: every AI recommendation is scored by an explainable deterministic engine first,
evaluated for schema validity/groundedness/confidence/safety/consistency, blocked
automatically on failure, routed to a human at defined risk thresholds, and every step is
written to a tamper-evident audit log. No AI output ever executes a real action — approved
actions are clearly marked simulations.

## Architecture summary

Modular monolith (FastAPI + SQLAlchemy + PostgreSQL), pragmatic OOP, one deployable
process. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full breakdown,
data-flow diagram, and vendor-independence strategy.

```
app/
├── api/            FastAPI routers, Pydantic schemas, error handling, middleware
├── domain/         enums, value objects, deterministic risk engine, workflow state machine
├── services/       orchestration: events, risk, AI recommendations, approvals, regression eval
├── repositories/   Protocol interfaces + PostgreSQL implementations
├── ai/
│   ├── providers/  AIProvider Protocol, mock provider (default), OpenAI-compatible provider
│   └── evaluation/ schema/grounding/confidence/safety/consistency gates, regression dataset
├── database/       SQLAlchemy models, engine/session
├── governance/     kill switch, approval-routing policy, lightweight identity/authz
├── monitoring/     Prometheus metrics, health/readiness
├── dashboard/       server-rendered read-only dashboard (Jinja2)
└── core/           settings, structured logging
```

## Key capabilities

- **Explainable deterministic risk engine** — rule-based, no AI dependency, same input
  always produces the same score/level/explanation.
- **Replaceable AI provider** — a deterministic local mock (default, no credentials) or an
  optional OpenAI-compatible HTTP provider, behind one `AIProvider` interface.
- **Mandatory evaluation gates** — schema validation, groundedness, confidence threshold,
  dangerous-action detection, and basic consistency checking, before anything reaches a
  human.
- **Fail-closed governance** — a local kill switch blocks AI processing and action
  simulation; failed evaluations block automatically; high/critical risk always requires
  human approval.
- **Full audit trail** — hash-chained, append-only audit log covering every transition.
- **Provider eligibility gate** — a new AI provider/model config must pass a versioned
  synthetic regression evaluation before it's used.
- **Vendor independence** — swap AI providers, swap PostgreSQL for another store (behind
  Protocols), swap AWS for GCP, all without touching risk rules, evaluation gates, approval
  logic, or the audit trail.

## Local setup

Requirements: Docker + Docker Compose, Python 3.12 (only needed if you want to run tests
or tooling outside the container).

```bash
cp .env.example .env          # edit values if you want; defaults work out of the box
docker compose up -d --build
docker compose exec app python -m alembic upgrade head
docker compose exec app python -m seed.seed_data
```

If the build fails with a certificate-verification error (some corporate/local networks
intercept TLS to PyPI), see the troubleshooting entry in
[`docs/RUNBOOK.md`](docs/RUNBOOK.md) — there's an opt-in build arg for that case; the
default build does full TLS verification.

## Docker Compose commands

| Action | Command |
| --- | --- |
| Start | `docker compose up -d --build` |
| Stop | `docker compose down` |
| Stop + wipe data | `docker compose down -v` |
| Logs | `docker compose logs -f app` |
| Shell in app container | `docker compose exec app bash` |

## Migration and seed commands

```bash
docker compose exec app python -m alembic upgrade head
docker compose exec app python -m alembic downgrade base   # rollback, for testing
docker compose exec app python -m seed.seed_data
```

## Test commands

Unit tests need no database. Integration/API/security/e2e tests need a real PostgreSQL —
the project never substitutes SQLite for these.

```bash
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt

pytest tests/unit -q                                          # no DB required
pytest tests/integration tests/api tests/security tests/e2e -q # requires TEST_DATABASE_URL reachable
```

With `docker compose up` already running, the compose Postgres exposes port 5432 on
localhost and `scripts/init-test-db.sql` has already created the `archguard_test`
database used by `TEST_DATABASE_URL` (see `tests/conftest.py` for the default).

Lint/format: `ruff check app tests migrations seed` and `ruff format app tests migrations seed`.

## API and dashboard access

- API: http://localhost:8000 — interactive docs at http://localhost:8000/docs
- Dashboard: http://localhost:8000/dashboard (read-only; state changes go through the API)
- Health: http://localhost:8000/health · Readiness: http://localhost:8000/ready · Metrics: http://localhost:8000/metrics

## Example demo workflow

All mutating endpoints require an `X-ArchGuard-Actor` header identifying the caller (see
[`docs/SECURITY.md`](docs/SECURITY.md) for the lightweight identity model). Approval
endpoints additionally require an `approver:` or `admin:` role prefix.

```bash
# 1. A provider/model config must pass regression evaluation before first use.
curl -s -X POST localhost:8000/providers/regression-evaluation \
  -H "X-ArchGuard-Actor: operator:demo" -H "Content-Type: application/json" -d '{}'

# 2. Create an incident.
EVENT=$(curl -s -X POST localhost:8000/events \
  -H "X-ArchGuard-Actor: operator:demo" -H "Content-Type: application/json" \
  -d '{"event_type":"availability_outage","source":"pagerduty","description":"Elevated 5xx on payments.","affected_service":"payments","environment":"production","severity":"high","evidence":["error rate 12%"]}')
EVENT_ID=$(echo "$EVENT" | python -c "import json,sys; print(json.load(sys.stdin)['id'])")

# 3. Deterministic risk assessment.
curl -s -X POST localhost:8000/events/$EVENT_ID/risk-assessment -H "X-ArchGuard-Actor: operator:demo"

# 4. AI recommendation + automated evaluation, in one call.
REC=$(curl -s -X POST localhost:8000/events/$EVENT_ID/recommendations -H "X-ArchGuard-Actor: operator:demo")
REC_ID=$(echo "$REC" | python -c "import json,sys; print(json.load(sys.stdin)['id'])")

# 5. Inspect the evaluation result.
curl -s localhost:8000/recommendations/$REC_ID/evaluation

# 6. Human approval (high risk -> requires approval).
curl -s -X POST localhost:8000/recommendations/$REC_ID/approval \
  -H "X-ArchGuard-Actor: approver:jane" -H "Content-Type: application/json" \
  -d '{"decision":"approved","reason":"matches runbook"}'

# 7. Full audit trail + final state.
curl -s localhost:8000/events/$EVENT_ID/audit
curl -s localhost:8000/events/$EVENT_ID
```

Or just open http://localhost:8000/dashboard after the seed script to see five
pre-populated scenarios (auto-cleared, approved, rejected, blocked-by-safety,
blocked-by-provider-failure).

## Safety restrictions

This project never: applies Terraform, creates/modifies/deletes real cloud resources,
executes a real operational action from an AI recommendation (actions are simulated and
clearly marked), logs secrets, or pushes to a remote repository. See
[`docs/SECURITY.md`](docs/SECURITY.md).

## Terraform validation commands

No cloud credentials are used or required. Only credential-free static checks run:

```bash
cd infrastructure/aws   # or infrastructure/gcp
terraform fmt -check
terraform init -backend=false
terraform validate
```

`terraform plan`/`apply` are intentionally not part of this workflow — see
[`docs/CLOUD_DESIGN.md`](docs/CLOUD_DESIGN.md) for the cost-safety statement and the exact
local validation results for this repository.

## Documentation

| Doc | Covers |
| --- | --- |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Component responsibilities, data flow, OOP decisions, vendor-independence strategy, diagram |
| [`docs/AI_ASSURANCE.md`](docs/AI_ASSURANCE.md) | Evaluation gates, grounding, confidence thresholds, safety validation, regression evaluation, kill-switch behavior, traceability |
| [`docs/QA_STRATEGY.md`](docs/QA_STRATEGY.md) | Test levels/environments, PostgreSQL strategy, security validation, E2E scope, known gaps |
| [`docs/CLOUD_DESIGN.md`](docs/CLOUD_DESIGN.md) | AWS/GCP architectures, service mapping, portability limits, cost-safety statement |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Threat assumptions, input validation, secret handling, the lightweight identity model, audit-integrity limitations |
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Start/stop/migrate/seed/test, troubleshooting, kill-switch and approval-flow walkthroughs, DB-outage recovery |
| [`docs/adr/`](docs/adr/) | The 5 architecture decisions and their trade-offs |

## Known limitations

- The dashboard is read-only by design; approvals go through the API so authorization stays
  in one place.
- The lightweight `X-ArchGuard-Actor` header identity model is intentionally not a real
  auth system — see `docs/SECURITY.md`.
- The OpenAI-compatible provider is implemented but not exercised by default (`AI_PROVIDER=mock`);
  it requires external credentials the POC does not ship.
- AWS uses public subnets for both compute and the database (no NAT/private tier) to keep
  the reference architecture lean; documented as a production-hardening gap in `docs/CLOUD_DESIGN.md`.
- No cloud deployment was performed or attempted; Terraform was validated statically only.

## Repository status

Local application, database, Docker Compose stack, and test suite are implemented and
verified end-to-end locally (see the project's final verification report for exact
pass/fail counts and commands run). No remote push has been performed.
