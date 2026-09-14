output "ecr_repository_url" {
  description = "Push application images here."
  value       = aws_ecr_repository.app.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  value = aws_ecs_service.app.name
}

output "rds_endpoint" {
  description = "PostgreSQL connection endpoint (host:port)."
  value       = aws_db_instance.main.endpoint
  sensitive   = true
}

output "db_credentials_secret_arn" {
  value = aws_secretsmanager_secret.db_credentials.arn
}

output "cloudwatch_log_group" {
  value = aws_cloudwatch_log_group.app.name
}
