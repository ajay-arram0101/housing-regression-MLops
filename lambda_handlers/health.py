"""
Lambda handler for /health endpoint
"""
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """Health check endpoint."""
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({
            "status": "healthy",
            "s3_bucket": os.environ.get("S3_BUCKET", "housing-regression-data-ajayr"),
            "function_version": context.function_version,
            "memory_limit_mb": context.memory_limit_in_mb,
            "aws_request_id": context.aws_request_id
        })
    }
