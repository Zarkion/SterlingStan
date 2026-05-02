variable "secret_name" {
  type = string
}

data "aws_secretsmanager_secret" "discord" {
  name = var.secret_name
}
