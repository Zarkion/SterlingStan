output "interactions_endpoint" {
  description = "Paste this URL into Discord Developer Portal > Interactions Endpoint URL"
  value       = module.api_gateway.invoke_url
}

output "registrar_function_name" {
  description = "Use this to invoke the Registrar manually after deploy"
  value       = module.lambda.registrar_function_name
}
