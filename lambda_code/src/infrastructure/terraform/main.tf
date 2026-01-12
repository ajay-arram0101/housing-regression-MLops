terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ============================================
# Data Sources
# ============================================

data "aws_caller_identity" "current" {}

data "aws_s3_bucket" "data" {
  bucket = var.s3_bucket_name
}

# ============================================
# IAM Role for Lambda
# ============================================

resource "aws_iam_role" "lambda_role" {
  name = "housing-prediction-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# Attach basic execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# S3 access policy
resource "aws_iam_role_policy" "lambda_s3_policy" {
  name = "lambda-s3-access"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          data.aws_s3_bucket.data.arn,
          "${data.aws_s3_bucket.data.arn}/*"
        ]
      }
    ]
  })
}

# ============================================
# CloudWatch Logs
# ============================================

resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/lambda/housing-prediction-api"
  retention_in_days = 30

  tags = var.tags
}

# ============================================
# Lambda Functions
# ============================================

resource "aws_lambda_function" "predict" {
  filename         = "lambda_functions/predict.zip"
  function_name    = "housing-predict"
  role             = aws_iam_role.lambda_role.arn
  handler          = "src.api.handlers.predict.lambda_handler"
  runtime          = "python3.11"
  memory_size      = 1024
  timeout          = 30
  source_code_hash = filebase64sha256("lambda_functions/predict.zip")

  layers = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      S3_BUCKET = var.s3_bucket_name
      AWS_REGION = var.aws_region
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_s3_policy,
    aws_iam_role_policy_attachment.lambda_basic_execution
  ]

  tags = var.tags
}

resource "aws_lambda_function" "health" {
  filename         = "lambda_functions/health.zip"
  function_name    = "housing-health"
  role             = aws_iam_role.lambda_role.arn
  handler          = "src.api.handlers.health.lambda_handler"
  runtime          = "python3.11"
  memory_size      = 256
  timeout          = 10
  source_code_hash = filebase64sha256("lambda_functions/health.zip")

  layers = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      S3_BUCKET = var.s3_bucket_name
      AWS_REGION = var.aws_region
    }
  }

  tags = var.tags
}

resource "aws_lambda_function" "batch" {
  filename         = "lambda_functions/batch.zip"
  function_name    = "housing-batch"
  role             = aws_iam_role.lambda_role.arn
  handler          = "src.api.handlers.batch.lambda_handler"
  runtime          = "python3.11"
  memory_size      = 2048
  timeout          = 900  # 15 minutes
  source_code_hash = filebase64sha256("lambda_functions/batch.zip")

  layers = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      S3_BUCKET = var.s3_bucket_name
      AWS_REGION = var.aws_region
    }
  }

  tags = var.tags
}

resource "aws_lambda_function" "predictions" {
  filename         = "lambda_functions/predictions.zip"
  function_name    = "housing-predictions"
  role             = aws_iam_role.lambda_role.arn
  handler          = "src.api.handlers.predictions.lambda_handler"
  runtime          = "python3.11"
  memory_size      = 256
  timeout          = 20
  source_code_hash = filebase64sha256("lambda_functions/predictions.zip")

  layers = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      S3_BUCKET = var.s3_bucket_name
      AWS_REGION = var.aws_region
    }
  }

  tags = var.tags
}

# ============================================
# Lambda Layer
# ============================================

resource "aws_lambda_layer_version" "dependencies" {
  filename                = "lambda_layers/dependencies.zip"
  layer_name              = "housing-prediction-dependencies"
  compatible_runtimes     = ["python3.11"]
  source_code_hash        = filebase64sha256("lambda_layers/dependencies.zip")
}

# ============================================
# API Gateway
# ============================================

resource "aws_apigatewayv2_api" "api" {
  name          = "housing-prediction-api"
  protocol_type = "HTTP"
  description   = "Housing Price Prediction API (Lambda Backend)"

  cors_configuration {
    allow_origins     = ["*"]
    allow_methods     = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers     = ["Content-Type", "Authorization"]
    expose_headers    = ["Content-Type"]
    max_age           = 300
  }

  tags = var.tags
}

# ============================================
# API Gateway Integrations & Routes
# ============================================

# Predict Integration
resource "aws_apigatewayv2_integration" "predict" {
  api_id           = aws_apigatewayv2_api.api.id
  integration_type = "AWS_PROXY"
  integration_method = "POST"
  payload_format_version = "2.0"
  target = aws_lambda_function.predict.arn
}

resource "aws_apigatewayv2_route" "predict" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "POST /predict"
  target    = "integrations/${aws_apigatewayv2_integration.predict.id}"
}

# Health Integration
resource "aws_apigatewayv2_integration" "health" {
  api_id           = aws_apigatewayv2_api.api.id
  integration_type = "AWS_PROXY"
  integration_method = "POST"
  payload_format_version = "2.0"
  target = aws_lambda_function.health.arn
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.health.id}"
}

# Batch Integration
resource "aws_apigatewayv2_integration" "batch" {
  api_id           = aws_apigatewayv2_api.api.id
  integration_type = "AWS_PROXY"
  integration_method = "POST"
  payload_format_version = "2.0"
  target = aws_lambda_function.batch.arn
}

resource "aws_apigatewayv2_route" "batch" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "POST /run_batch"
  target    = "integrations/${aws_apigatewayv2_integration.batch.id}"
}

# Predictions Integration
resource "aws_apigatewayv2_integration" "predictions" {
  api_id           = aws_apigatewayv2_api.api.id
  integration_type = "AWS_PROXY"
  integration_method = "POST"
  payload_format_version = "2.0"
  target = aws_lambda_function.predictions.arn
}

resource "aws_apigatewayv2_route" "predictions" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "GET /latest_predictions"
  target    = "integrations/${aws_apigatewayv2_integration.predictions.id}"
}

# ============================================
# API Gateway Stage
# ============================================

resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "prod"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      integrationLatency = "$context.integration.latency"
    })
  }

  tags = var.tags
}

# ============================================
# Lambda Permissions (for API Gateway invocation)
# ============================================

resource "aws_lambda_permission" "predict_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.predict.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*"
}

resource "aws_lambda_permission" "health_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.health.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*"
}

resource "aws_lambda_permission" "batch_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.batch.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*"
}

resource "aws_lambda_permission" "predictions_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.predictions.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*"
}
