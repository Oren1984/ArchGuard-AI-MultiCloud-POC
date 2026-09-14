# Managed PostgreSQL. Cloud Run connects via the native Cloud SQL
# integration (unix socket over the Cloud SQL Auth Proxy that Cloud Run
# manages for you) — no VPC connector needed for this POC, unlike the AWS
# design's RDS-in-VPC approach. See docs/CLOUD_DESIGN.md for the boundary
# this creates (GCP path is simpler; AWS path is more explicit/portable).

resource "random_password" "db_password" {
  length  = 24
  special = false
}

resource "google_sql_database_instance" "main" {
  name             = "${var.project_name}-db"
  database_version = "POSTGRES_16"
  region           = var.gcp_region

  settings {
    tier              = var.db_tier
    availability_type = "ZONAL"

    backup_configuration {
      enabled = true
    }

    ip_configuration {
      ipv4_enabled = true
      # POC default: public IP restricted to Cloud SQL's own authorized-network
      # allowlist is not configured here — production should add authorized
      # networks or a private-IP + VPC connector setup instead.
    }
  }

  deletion_protection = false
}

resource "google_sql_database" "app" {
  name     = var.db_name
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "app" {
  name     = var.db_username
  instance = google_sql_database_instance.main.name
  password = random_password.db_password.result
}
