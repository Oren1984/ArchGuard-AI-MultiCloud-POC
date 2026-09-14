# Cloud Design

AWS-primary, GCP-secondary. Both are lean reference architectures for running the same
application container + PostgreSQL database — not a shared abstracted module, two
independent Terraform configurations that happen to provision comparable capabilities.

## AWS primary architecture (`infrastructure/aws/`)

| Concern | Resource | File |
| --- | --- | --- |
| Networking | VPC, 2 public subnets across 2 AZs, IGW, route table, 2 security groups (app: inbound 8000; db: inbound 5432 from app SG only) | `network.tf` |
| Application compute | ECS Fargate cluster/task/service, `awsvpc` networking, public IP, no ALB | `ecs.tf` |
| PostgreSQL | RDS `db.t4g.micro`, `postgres16`, encrypted storage, `db_subnet_group` across both public subnets | `rds.tf` |
| Secret/config management | Secrets Manager: one secret for DB credentials, one for app config (AI provider settings) | `secrets.tf` |
| Monitoring/logging | CloudWatch log group for ECS task stdout (carries the app's structured JSON logs) | `logs.tf` |
| Container image storage | ECR repository, immutable tags, scan-on-push, 10-image lifecycle policy | `ecr.tf` |
| IAM | Execution role scoped to ECR pull + CloudWatch logs + the two named secrets; task role starts with zero extra permissions (the app makes no AWS SDK calls) | `iam.tf` |

## GCP secondary architecture (`infrastructure/gcp/`)

| Concern | Resource | File |
| --- | --- | --- |
| Application compute | Cloud Run v2 service, public ingress (`allUsers` invoker for POC demo purposes) | `run.tf` |
| PostgreSQL | Cloud SQL for PostgreSQL 16, `db-f1-micro`, connected via Cloud Run's native Cloud SQL integration (no VPC connector needed) | `cloudsql.tf` |
| Secret/config management | Secret Manager: same two-secret split as AWS, granted to a dedicated Cloud Run service account | `secrets.tf`, `run.tf` |
| Monitoring/logging | Cloud Logging is automatic for Cloud Run — no explicit log resource needed | *(implicit)* |
| Container image storage | Artifact Registry (Docker format) repository | `artifact_registry.tf` |
| IAM | Dedicated `google_service_account` for Cloud Run with `secretAccessor` on exactly the two secrets it needs | `run.tf` |

GCP needed noticeably less networking glue than AWS for the same capability (no VPC/subnet
definitions at all) because Cloud Run's native Cloud SQL integration and Google-managed
ingress absorb what AWS requires explicit VPC/subnet/security-group resources for — a real,
demonstrated architectural difference between the providers, not an oversight in one
config.

## Service mapping

| Capability | AWS | GCP |
| --- | --- | --- |
| Application compute | ECS Fargate | Cloud Run |
| PostgreSQL | RDS for PostgreSQL | Cloud SQL for PostgreSQL |
| Secrets | Secrets Manager | Secret Manager |
| Container registry | ECR | Artifact Registry |
| Logs | CloudWatch Logs | Cloud Logging (automatic) |
| Compute identity | ECS task role/execution role | Cloud Run service account |

## Shared vs. provider-specific boundary

**Shared (identical regardless of cloud):** the entire `app/` Python package — risk rules,
evaluation gates, approval routing, audit trail, kill switch, workflow states. Nothing in
`app/` imports a cloud SDK. Portability is achieved by keeping all cloud specifics in
environment variables consumed by `app/core/config.py` (`DATABASE_URL`, `AI_PROVIDER`,
etc.) and in the two independent Terraform trees — never in application code.

**Provider-specific (not portable, by design):** the Terraform resource types themselves
(ECS vs. Cloud Run, RDS vs. Cloud SQL, Secrets Manager vs. Secret Manager), the AWS VPC/subnet/security-group
networking layer (GCP's Cloud Run doesn't need an equivalent for this POC's connectivity
model), and IAM shapes (AWS IAM roles/policies vs. GCP service accounts/IAM bindings).

## Portability limitations — stated honestly

- This is **not** a "write once, deploy to either cloud" abstraction. Migrating from AWS to
  GCP means running a different Terraform tree, not flipping a variable.
- The AWS design uses public subnets for both compute and the database (no NAT gateway) to
  keep the reference architecture lean for a POC. A production deployment should move the
  database (and ideally the app) into private subnets behind a NAT gateway.
- Neither design fronts the application with a load balancer/API gateway or TLS
  termination — the AWS Fargate service is reachable directly on its public IP, and Cloud
  Run's `allUsers` invoker binding is a POC convenience, not a production access-control
  posture. Both are flagged here, not silently shipped as if production-ready.
- Vendor-specific behaviors (RDS's specific backup/maintenance windows, Cloud SQL's
  specific Cloud Run integration mechanics) are not abstracted — using either database
  correctly still requires provider-specific operational knowledge.

## Cost-safety statement

No cloud account, credentials, or billing information was used, requested, or referenced
at any point. All Terraform commands executed were limited to `fmt`, `init -backend=false`,
and an attempted `validate` — none of which contact a cloud provider's API or create any
billable resource. `terraform plan` and `terraform apply` were never run.

## Terraform validation results (this repository, this session)

| Command | AWS | GCP |
| --- | --- | --- |
| `terraform fmt -check` | ✅ Pass (after one auto-format pass) | ✅ Pass (after one auto-format pass) |
| `terraform init -backend=false` | ✅ Pass — providers `hashicorp/aws ~> 5.0`, `hashicorp/random ~> 3.6` resolved and locked | ✅ Pass — providers `hashicorp/google ~> 5.0`, `hashicorp/random ~> 3.6` resolved and locked |
| `terraform validate` | ⚠️ Could not execute in this sandbox | ⚠️ Could not execute in this sandbox |
| `terraform plan` | Not attempted (requires cloud credentials, which this POC does not use) | Not attempted (requires cloud credentials) |

**`terraform validate` limitation, stated accurately:** in this specific sandboxed
execution environment, `terraform validate` fails for *both* configurations with an
identical, configuration-independent error: `x509: certificate signed by unknown
authority` during Terraform's own local loopback handshake with the downloaded provider
plugin binary (not a network call to AWS/GCP — this handshake never leaves 127.0.0.1). The
environment has a local TLS-inspecting security/monitoring agent (evidenced by
`SSLKEYLOGFILE` pointing at a named pipe of a local monitoring proxy) that intercepts this
loopback TLS handshake and breaks Terraform's plugin protocol, independent of anything in
this repository's `.tf` files. The same `docker build` step for this project's application
image hit the identical class of interception against pypi.org and required a documented,
non-committed local workaround (see the project's final verification report) — confirming
this is a machine-level environment constraint, not a configuration defect. Both
configurations were manually reviewed for correctness, formatted, and successfully
initialized against the real Terraform Registry; `validate`/`plan` should be re-run on a
standard CI runner or a developer machine without local TLS interception before treating
this as a completed check.
