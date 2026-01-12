variable "aws_region" {
  type        = string
  default     = "us-east-2"
  description = "AWS region for deployment"
}

variable "s3_bucket_name" {
  type        = string
  default     = "housing-regression-data-ajayr"
  description = "S3 bucket name for models and data"
}

variable "project_name" {
  type        = string
  default     = "housing-prediction"
  description = "Project name for resource naming"
}

variable "environment" {
  type        = string
  default     = "prod"
  description = "Environment (prod, staging, dev)"
}

variable "tags" {
  type = map(string)
  default = {
    Project     = "housing-prediction"
    ManagedBy   = "terraform"
    Environment = "prod"
    MigrationDate = "2025-01-10"
  }
  description = "Common tags for all resources"
}
