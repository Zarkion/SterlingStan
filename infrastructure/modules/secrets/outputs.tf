output "secret_arn" {
  value = data.aws_secretsmanager_secret.discord.arn
}
