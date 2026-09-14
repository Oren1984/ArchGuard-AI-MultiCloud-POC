# Secret/configuration management.

resource "google_secret_manager_secret" "db_credentials" {
  secret_id = "${var.project_name}-db-credentials"
  labels    = var.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_credentials" {
  secret = google_secret_manager_secret.db_credentials.id
  secret_data = jsonencode({
    username                 = var.db_username
    password                 = random_password.db_password.result
    dbname                   = var.db_name
    instance_connection_name = google_sql_database_instance.main.connection_name
  })
}

resource "google_secret_manager_secret" "app_config" {
  secret_id = "${var.project_name}-app-config"
  labels    = var.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "app_config" {
  secret = google_secret_manager_secret.app_config.id
  secret_data = jsonencode({
    AI_PROVIDER       = "mock"
    AI_MODEL_NAME     = "archguard-mock-v1"
    AI_PROMPT_VERSION = "v1"
  })
}
