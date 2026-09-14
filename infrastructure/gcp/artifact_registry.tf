# Container image storage.

resource "google_artifact_registry_repository" "app" {
  repository_id = "${var.project_name}-app"
  location      = var.gcp_region
  format        = "DOCKER"
  description   = "ArchGuard POC application images."
  labels        = var.labels
}
