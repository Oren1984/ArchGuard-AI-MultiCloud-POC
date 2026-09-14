# ADR 0004: AWS-primary, GCP-secondary — two independent Terraform trees, not one abstracted module

## Status

Accepted

## Context

The spec requires demonstrating AWS as the primary cloud target and GCP as a secondary
target, showing that the application isn't locked to one vendor, while explicitly
warning: "Do not falsely claim perfect cloud portability. Clearly identify shared
components and provider-specific infrastructure," and "Avoid unnecessary modules and
abstractions for this POC."

## Decision

Write two separate, independent Terraform configurations (`infrastructure/aws/`,
`infrastructure/gcp/`) that provision *comparable capabilities* (compute, managed
PostgreSQL, secrets, logging, image registry) using each provider's idiomatic services —
ECS Fargate + RDS + Secrets Manager + ECR on AWS; Cloud Run + Cloud SQL + Secret Manager +
Artifact Registry on GCP — rather than one templated module with provider-conditional
resource blocks.

## Consequences

- No shared Terraform module means no leaky cross-provider abstraction to maintain, and
  each config reads as an idiomatic example for its own provider (a GCP engineer isn't
  stuck reading an AWS-shaped abstraction).
- Portability lives entirely at the *application* layer (env-var-driven config, no cloud
  SDK imports in `app/`) — proven by the fact that the same container image and the same
  `docker-compose.yml` demo require zero code changes regardless of which cloud eventually
  hosts it.
- The two configs are honestly *not* symmetric: GCP's design needs no explicit
  VPC/subnet/security-group resources (Cloud Run's native Cloud SQL integration absorbs
  that), while AWS's does. This asymmetry is documented in `docs/CLOUD_DESIGN.md` rather
  than forced into artificial symmetry.
- Both configs are validated identically (`fmt`, `init -backend=false`, `validate`) and
  neither is ever applied — no real cloud spend or resource risk from this decision.
