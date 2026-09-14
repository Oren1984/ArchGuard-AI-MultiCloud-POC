terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # No remote backend configured for this POC — state stays local and no
  # backend credentials are required to run `terraform init -backend=false`.
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}
