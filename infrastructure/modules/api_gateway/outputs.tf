output "invoke_url" {
  value       = "${aws_apigatewayv2_stage.default.invoke_url}/interactions"
  description = "Paste this into Discord Developer Portal > Interactions Endpoint URL"
}
