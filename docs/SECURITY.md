# Security

## Threat assumptions

This is a local demonstration POC, not a hardened production system. It assumes: a single
trusted network (Docker Compose bridge network / localhost), no hostile multi-tenant
access to the database, and an operator running the stack who has legitimate access to the
machine it runs on. It does **not** assume the AI provider's output is trustworthy — that
assumption is exactly what the evaluation gates in `docs/AI_ASSURANCE.md` exist to remove.

## Input validation

All external input crosses strict Pydantic models (`app/api/schemas.py`) with
`extra="forbid"`, explicit length bounds (`MAX_TEXT=4000`, `MAX_SHORT_TEXT=256`,
`MAX_EVIDENCE_ITEMS=20`), and enum membership checks — an invalid `event_type` or an
oversized `description` is rejected with `422` before it reaches any service code. All
persistence goes through SQLAlchemy's parameterized queries; there is no raw SQL string
interpolation anywhere in the codebase, so SQL-injection-shaped input (tested in
`tests/security/test_input_validation.py`) is stored as inert data, never executed.
Responses are JSON, not server-rendered HTML from user input, so script-tag-shaped input in
a description is returned as plain text, not executed — the one place user data *is*
rendered as HTML is the read-only dashboard, which relies on Jinja2's default autoescaping
(on by default for `.html` templates) rather than any manual escaping.

## Secret handling

- `.env.example` contains only placeholders (`changeme-local-only`), never a real
  credential — verified by `tests/security/test_secret_exposure.py::test_env_example_has_no_real_looking_secrets`.
- `app/core/logging.py::RedactingJsonFormatter` redacts any log field named `password`,
  `api_key`, `secret`, `token`, or `authorization` (case-insensitive) to `***REDACTED***`
  before it's written — verified in `tests/unit/test_logging_redaction.py`.
- The catch-all exception handler (`app/api/error_handlers.py`) never returns exception
  internals to the client — only a generic `error`/`detail`/`correlation_id` triple, even
  when the underlying exception message contains something sensitive-looking (proven by
  deliberately raising a `RuntimeError` with a fake password in it in
  `tests/security/test_secret_exposure.py`).
- `.env` (the real, populated file) is git-ignored; Terraform `.tfvars` files are
  git-ignored; nothing under `secrets/` is ever committed.

## Approval protection — the lightweight identity model

This POC deliberately does **not** implement a full authentication platform (no password
storage, no sessions, no tokens) — that would be disproportionate scope for a POC whose
point is demonstrating the *governance workflow*, not building an identity provider. What
it does implement, to make approval accountability meaningfully testable:

- Every mutating endpoint requires an `X-ArchGuard-Actor` header identifying the caller.
  Missing or malformed (`app/governance/identity.py::require_actor`, a strict regex —
  no whitespace-only values, no control characters, alphanumeric/`_.:-` only) → `403`.
- Approval/rejection additionally requires the actor string to start with `approver:` or
  `admin:`; the kill switch additionally requires `admin:`. An `operator:`-prefixed actor
  that can create events and request AI recommendations is explicitly forbidden from
  approving its own recommendation or touching the kill switch — enforced in
  `app/api/routers/recommendations.py` and `app/api/routers/kill_switch.py`, tested in
  `tests/security/test_approval_authorization.py`.
- Every approval decision records `approver_identity` verbatim in `approval_decisions`, so
  the audit trail always answers "who approved this" — including the `system:auto-clear`
  identity used for the no-human-approval-required path, so that path is never silently
  unattributed either.

**Honest limitation:** this is a self-asserted identity (the caller states who they are via
a header) with no cryptographic verification — anyone who can reach the API can claim to be
`approver:jane`. That is an acceptable trade-off for a local POC demonstrating the
*workflow*, and would need to be replaced with real authentication (OIDC/mTLS/API keys
tied to a real identity provider) before any non-demo use.

## Audit integrity — what the hash chain does and doesn't guarantee

`audit_logs` is hash-chained: `record_hash = sha256(previous_hash + canonical(actor,
action, details, event_id))`, ordered by a database-generated monotonic `seq` column
(`Identity()`, not the UUID primary key, so ordering survives even if primary keys were
ever non-sequential). `AuditRepository.verify_chain()` replays the whole chain and detects
any row whose stored hash no longer matches its recomputed hash, or whose `previous_hash`
no longer matches its predecessor — proven by
`tests/integration/test_repositories.py::test_audit_hash_chain_detects_tampering`, which
mutates a row's `details` in place and confirms `verify_chain()` returns `False`.

**This gives tamper-*evidence* on replay, not tamper-*prevention* or cryptographic
immutability.** It does not: prevent someone with direct database write access from
rewriting the entire chain consistently (only external anchoring — e.g., periodically
publishing the latest hash to an external, append-only system — would close that gap, and
this POC does not implement that); protect against deletion of the *entire* table; or
provide non-repudiation in a legal sense. It is sufficient to detect accidental corruption
or a naive in-place edit, which is the bar appropriate for a POC's audit trail.

## Dependency and container considerations

- Runtime dependencies are pinned to exact versions in `requirements.txt` (not open ranges),
  so builds are reproducible.
- The application container runs as a non-root user (`archguard`, uid 1000), created
  explicitly in the `Dockerfile` rather than running as the image's default root user.
- The container includes only `curl` beyond the Python runtime (needed for its own
  `HEALTHCHECK`) — no build toolchain or unnecessary packages ship in the final image.
- `docker-compose.yml` never exposes the database beyond `localhost:5432` and never bakes a
  real credential into the image — the `.env` file is mounted via `env_file:`, not `COPY`'d
  into the image.

## POC limitations (explicitly out of scope)

- No TLS termination for the local HTTP API (POC runs plaintext HTTP on localhost).
- No rate limiting / brute-force protection on any endpoint.
- No secrets-manager integration for local runs (`.env` is a local file) — Terraform *does*
  model Secrets Manager / Secret Manager for the cloud designs (`docs/CLOUD_DESIGN.md`),
  but the local Docker Compose stack intentionally stays simple.
- No dependency vulnerability scanning is wired into CI (would be a reasonable next step —
  `pip-audit` or GitHub's Dependabot — but was out of scope for this POC's CI workflow to
  keep it "concise... not a large CI platform" per the project's own stated constraint).
