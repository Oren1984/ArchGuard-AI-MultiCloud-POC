# Monitoring/logging: CloudWatch log group for ECS task stdout/stderr, which
# carries the app's structured JSON logs (app/core/logging.py).

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 14
  tags              = var.tags
}
