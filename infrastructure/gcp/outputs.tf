output "artifact_registry_repository" {
  description = "Push application images here."
  value       = google_artifact_registry_repository.app.name
}

output "cloud_run_service_url" {
  value = google_cloud_run_v2_service.app.uri
}

output "cloudsql_connection_name" {
  description = "Instance connection name for the Cloud SQL Auth Proxy / Cloud Run integration."
  value       = google_sql_database_instance.main.connection_name
  sensitive   = true
}

output "db_credentials_secret_id" {
  value = google_secret_manager_secret.db_credentials.secret_id
}
