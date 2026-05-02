variable "project_name" { type = string }
variable "verifier_function_arn" { type = string }

resource "aws_cloudwatch_event_rule" "warmup" {
  name                = "${var.project_name}-warmup"
  description         = "Keeps the Verifier Lambda warm to prevent cold-start timeouts"
  schedule_expression = "rate(10 minutes)"
}

resource "aws_cloudwatch_event_target" "warmup" {
  rule  = aws_cloudwatch_event_rule.warmup.name
  arn   = var.verifier_function_arn
  input = jsonencode({ source = "sterlingstan.warmup" })
}

resource "aws_lambda_permission" "eventbridge_warmup" {
  statement_id  = "AllowEventBridgeWarmup"
  action        = "lambda:InvokeFunction"
  function_name = var.verifier_function_arn
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.warmup.arn
}
