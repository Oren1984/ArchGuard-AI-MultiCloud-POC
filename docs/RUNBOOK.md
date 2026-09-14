# Runbook

All commands assume the repository root as the working directory.

## Start

```bash
cp .env.example .env            # first time only
docker compose up -d --build
docker compose exec app python -m alembic upgrade head
docker compose exec app python -m seed.seed_data   # optional, populates 5 demo scenarios
```

## Stop

```bash
docker compose down          # stop and remove containers, keep the data volume
docker compose down -v       # also delete the PostgreSQL data volume (irreversible)
```

## Migrate

```bash
docker compose exec app python -m alembic upgrade head      # apply all pending migrations
docker compose exec app python -m alembic downgrade -1      # roll back one revision
docker compose exec app python -m alembic downgrade base    # roll back everything
docker compose exec app python -m alembic current           # show applied revision
```

## Seed

```bash
docker compose exec app python -m seed.seed_data
```

Idempotency note: re-running the seed script creates a *new* set of five events rather than
upserting — it's meant for populating a fresh database, not for repeated demo resets. To
reset cleanly: `docker compose down -v && docker compose up -d --build`, then migrate and
seed again.

## Test

```bash
# From the host, with a venv:
python -m venv .venv && .venv/Scripts/activate   # or: source .venv/bin/activate
pip install -r requirements-dev.txt

pytest tests/unit -q                                            # no DB needed
pytest tests/integration tests/api tests/security tests/e2e -q  # needs docker compose up (Postgres on :5432)
```

## Troubleshoot

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `docker compose up` hangs on `db` health check | Postgres still initializing | `docker compose logs db` — wait for `database system is ready to accept connections` |
| App container `unhealthy` | Migrations not yet applied, or DB unreachable | `docker compose logs app`; confirm `db` is healthy first; re-run `alembic upgrade head` |
| `GET /ready` returns `503` | Database unavailable (see the dedicated procedure below) | `docker compose ps db`; `docker compose restart db` |
| Tests skip with "PostgreSQL not reachable" | `docker compose up` isn't running, or `TEST_DATABASE_URL` doesn't match | Start compose; confirm port 5432 is published (`docker compose port db 5432`) |
| `POST /events/{id}/recommendations` returns `409 ProviderNotEligibleError` | No passing regression-evaluation record for the current provider/model config | `POST /providers/regression-evaluation` first (see the demo flow in `README.md`) |
| `POST .../recommendations` or `/approval` returns `423 Locked` | Kill switch is active | See "Deactivate the kill switch" below |
| `docker compose build` fails with `CERTIFICATE_VERIFY_FAILED` during `pip install` | A local/corporate network is running a TLS-inspecting proxy that breaks pip's certificate verification against PyPI from inside the build container | Set `PIP_TRUSTED_HOST_ARGS` before building — **only on networks where you've confirmed this is the cause**, since it disables certificate verification for those hosts: `PIP_TRUSTED_HOST_ARGS="--trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org" docker compose build` (or add it to `.env`, which `docker compose` reads for variable substitution). Leave unset on any network without this problem — the default build does full TLS verification. |

## Activate and deactivate the kill switch

```bash
# Activate (requires an admin:-prefixed actor):
curl -X POST localhost:8000/governance/kill-switch/activate \
  -H "X-ArchGuard-Actor: admin:oncall" -H "Content-Type: application/json" \
  -d '{"reason":"incident drill"}'

# Confirm state:
curl localhost:8000/governance/kill-switch

# While active: AI recommendation requests return 423 and the event is
# transitioned to `blocked`, fully audited — this is the expected fail-closed
# behavior, not an error to work around.

# Deactivate:
curl -X POST localhost:8000/governance/kill-switch/deactivate \
  -H "X-ArchGuard-Actor: admin:oncall" -H "Content-Type: application/json" \
  -d '{"reason":"drill complete"}'
```

## Demonstrate the approval flow

```bash
curl -X POST localhost:8000/providers/regression-evaluation \
  -H "X-ArchGuard-Actor: operator:demo" -H "Content-Type: application/json" -d '{}'

EVENT_ID=$(curl -s -X POST localhost:8000/events \
  -H "X-ArchGuard-Actor: operator:demo" -H "Content-Type: application/json" \
  -d '{"event_type":"availability_outage","source":"pagerduty","description":"Elevated 5xx on payments.","affected_service":"payments","environment":"production","severity":"high","evidence":["error rate 12%"]}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['id'])")

curl -X POST localhost:8000/events/$EVENT_ID/risk-assessment -H "X-ArchGuard-Actor: operator:demo"

REC_ID=$(curl -s -X POST localhost:8000/events/$EVENT_ID/recommendations \
  -H "X-ArchGuard-Actor: operator:demo" | python -c "import json,sys; print(json.load(sys.stdin)['id'])")

# High risk -> requires human approval. Try approving as an unauthorized role first:
curl -X POST localhost:8000/recommendations/$REC_ID/approval \
  -H "X-ArchGuard-Actor: operator:demo" -H "Content-Type: application/json" \
  -d '{"decision":"approved"}'    # expect 403

# Approve as an authorized role:
curl -X POST localhost:8000/recommendations/$REC_ID/approval \
  -H "X-ArchGuard-Actor: approver:jane" -H "Content-Type: application/json" \
  -d '{"decision":"approved","reason":"matches runbook"}'

curl localhost:8000/events/$EVENT_ID/audit           # full transition history
curl "localhost:8000/audit/verify"                   # hash-chain integrity check
open http://localhost:8000/dashboard/events/$EVENT_ID # or curl -s | less on Linux/macOS
```

## Recover from database unavailability

```bash
docker compose stop db
curl -s localhost:8000/ready     # {"ready":false,"database_available":false}, HTTP 503
docker compose start db
# wait for health check:
docker compose ps db
curl -s localhost:8000/ready     # {"ready":true,"database_available":true}
```

The app process itself does not crash when the database goes away — `/health` (liveness)
stays `200` throughout; only `/ready` (readiness) reflects the outage, which is the correct
signal for an orchestrator to stop routing traffic without killing the process.

## Validate Terraform safely

```bash
cd infrastructure/aws   # then repeat for infrastructure/gcp
terraform fmt -check
terraform init -backend=false
terraform validate      # credential-free; does not contact AWS/GCP
```

Never run `terraform plan` or `terraform apply` against real credentials as part of this
POC — see `docs/CLOUD_DESIGN.md` for why and for this session's actual validation results.
