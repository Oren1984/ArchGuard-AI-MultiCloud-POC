# Secret/configuration management. Value is left as a placeholder — actual
# credentials are provisioned out-of-band (CI/CD secret injection or manual
# `aws secretsmanager put-secret-value`), never committed here.

resource "random_password" "db_password" {
  length  = 24
  special = false
}

resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "${var.project_name}/db-credentials"
  description = "PostgreSQL master credentials for the ArchGuard POC."
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db_password.result
    dbname   = var.db_name
    host     = aws_db_instance.main.address
    port     = 5432
  })
}

resource "aws_secretsmanager_secret" "app_config" {
  name        = "${var.project_name}/app-config"
  description = "Non-database application configuration (AI provider settings, etc.)."
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "app_config" {
  secret_id = aws_secretsmanager_secret.app_config.id
  secret_string = jsonencode({
    AI_PROVIDER       = "mock"
    AI_MODEL_NAME     = "archguard-mock-v1"
    AI_PROMPT_VERSION = "v1"
  })
}
