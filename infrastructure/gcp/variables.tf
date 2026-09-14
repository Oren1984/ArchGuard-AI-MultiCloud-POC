variable "gcp_project_id" {
  description = "GCP project ID to deploy into. No default — must be supplied explicitly so nothing is accidentally planned/applied against the wrong project."
  type        = string
  default     = "PLACEHOLDER_PROJECT_ID"
}

variable "gcp_region" {
  description = "GCP region for all resources."
  type        = string
  default     = "us-central1"
}

variable "project_name" {
  description = "Short name used to prefix/label resources."
  type        = string
  default     = "archguard-poc"
}

variable "environment" {
  description = "Deployment environment label."
  type        = string
  default     = "poc"
}

variable "container_image" {
  description = "Full Artifact Registry image URI (repo/image:tag). Placeholder until an image has been pushed."
  type        = string
  default     = "PLACEHOLDER_IMAGE_URI"
}

variable "container_port" {
  description = "Port the application container listens on."
  type        = number
  default     = 8000
}

variable "cloud_run_cpu" {
  description = "Cloud Run CPU allocation."
  type        = string
  default     = "1"
}

variable "cloud_run_memory" {
  description = "Cloud Run memory allocation."
  type        = string
  default     = "512Mi"
}

variable "db_tier" {
  description = "Cloud SQL machine tier. Smallest practical tier for a POC."
  type        = string
  default     = "db-f1-micro"
}

variable "db_name" {
  description = "Application database name."
  type        = string
  default     = "archguard"
}

variable "db_username" {
  description = "Application database username."
  type        = string
  default     = "archguard"
}

variable "labels" {
  description = "Common resource labels."
  type        = map(string)
  default = {
    project = "archguard-ai-multicloud-poc"
    managed = "terraform"
  }
}
