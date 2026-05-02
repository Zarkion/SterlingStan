output "table_name" {
  value = aws_dynamodb_table.members.name
}

output "table_arn" {
  value = aws_dynamodb_table.members.arn
}
