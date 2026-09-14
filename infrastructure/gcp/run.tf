# Application compute: Cloud Run (serverless containers) — the GCP-idiomatic
# equivalent of the AWS ECS Fargate service, with less infrastructure to
# define (no VPC/subnets required for this POC's connectivity model).

resource "google_service_account" "run_sa" {
  account_id   = "${var.project_name}-run-sa"
  display_name = "ArchGuard POC Cloud Run service account"
}

resource "google_secret_manager_secret_iam_member" "run_sa_db_secret" {
  secret_id = google_secret_manager_secret.db_credentials.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.run_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "run_sa_app_secret" {
  secret_id = google_secret_manager_secret.app_config.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.run_sa.email}"
}

resource "google_cloud_run_v2_service" "app" {
  name     = "${var.project_name}-app"
  location = var.gcp_region
  labels   = var.labels

  template {
    service_account = google_service_account.run_sa.email

    containers {
      image = var.container_image

      ports {
        container_port = var.container_port
      }

      resources {
        limits = {
          cpu    = var.cloud_run_cpu
          memory = var.cloud_run_memory
        }
      }

      env {
        name  = "APP_ENV"
        value = var.environment
      }
      env {
        name  = "APP_PORT"
        value = tostring(var.container_port)
      }
      env {
        name = "DB_CREDENTIALS_JSON"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_credentials.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "APP_CONFIG_JSON"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.app_config.secret_id
            version = "latest"
          }
        }
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.main.connection_name]
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# POC-only public ingress. Production should front this with IAM-based
# access or an API gateway instead of allUsers.
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  name     = google_cloud_run_v2_service.app.name
  location = google_cloud_run_v2_service.app.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
