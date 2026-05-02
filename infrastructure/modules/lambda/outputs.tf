output "verifier_invoke_arn" { value = aws_lambda_function.verifier.invoke_arn }
output "verifier_function_arn" { value = aws_lambda_function.verifier.arn }
output "executor_arn" { value = aws_lambda_function.executor.arn }
output "registrar_function_name" { value = aws_lambda_function.registrar.function_name }
