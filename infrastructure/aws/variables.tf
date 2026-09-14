variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name used to prefix/tag resources."
  type        = string
  default     = "archguard-poc"
}

variable "environment" {
  description = "Deployment environment label."
  type        = string
  default     = "poc"
}

variable "container_image" {
  description = "Full ECR image URI (repository:tag) for the application container. Left as a placeholder until an image has been pushed."
  type        = string
  default     = "PLACEHOLDER_IMAGE_URI"
}

variable "container_port" {
  description = "Port the application container listens on."
  type        = number
  default     = 8000
}

variable "task_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate task memory (MiB)."
  type        = number
  default     = 1024
}

variable "db_instance_class" {
  description = "RDS instance class. Smallest practical class for a POC."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage_gb" {
  description = "RDS allocated storage in GB."
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Application database name."
  type        = string
  default     = "archguard"
}

variable "db_username" {
  description = "Master database username."
  type        = string
  default     = "archguard"
}

variable "vpc_cidr" {
  description = "CIDR block for the POC VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for the two public subnets (ECS + RDS for POC simplicity)."
  type        = list(string)
  default     = ["10.42.1.0/24", "10.42.2.0/24"]
}

variable "tags" {
  description = "Common resource tags."
  type        = map(string)
  default = {
    Project = "archguard-ai-multicloud-poc"
    Managed = "terraform"
  }
}
