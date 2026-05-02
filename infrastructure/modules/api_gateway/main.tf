variable "project_name" { type = string }
variable "verifier_invoke_arn" { type = string }
variable "verifier_function_arn" { type = string }

resource "aws_apigatewayv2_api" "sterlingstan" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"
  description   = "SterlingStan Discord interactions endpoint"
}

resource "aws_apigatewayv2_integration" "verifier" {
  api_id                 = aws_apigatewayv2_api.sterlingstan.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.verifier_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "interactions" {
  api_id    = aws_apigatewayv2_api.sterlingstan.id
  route_key = "POST /interactions"
  target    = "integrations/${aws_apigatewayv2_integration.verifier.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.sterlingstan.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.verifier_function_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.sterlingstan.execution_arn}/*/*"
}
