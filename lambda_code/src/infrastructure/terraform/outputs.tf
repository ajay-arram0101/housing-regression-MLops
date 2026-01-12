output "api_endpoint" {
  value       = aws_apigatewayv2_api.api.api_endpoint
  description = "API Gateway endpoint URL"
}

output "predict_function_arn" {
  value       = aws_lambda_function.predict.arn
  description = "Predict Lambda function ARN"
}

output "health_function_arn" {
  value       = aws_lambda_function.health.arn
  description = "Health Lambda function ARN"
}

output "batch_function_arn" {
  value       = aws_lambda_function.batch.arn
  description = "Batch Lambda function ARN"
}

output "predictions_function_arn" {
  value       = aws_lambda_function.predictions.arn
  description = "Predictions Lambda function ARN"
}

output "lambda_role_arn" {
  value       = aws_iam_role.lambda_role.arn
  description = "Lambda execution role ARN"
}

output "cloudwatch_log_group" {
  value       = aws_cloudwatch_log_group.api_logs.name
  description = "CloudWatch log group for API logs"
}
