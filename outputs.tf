output "lambda_function_arn" {
  description = "The ARN of the Lambda function."
  value       = module.lambda.function_arn
}

output "lambda_function_name" {
  description = "The name of the Lambda function."
  value       = module.lambda.function_name
}
