from pathlib import Path
from src.api.utils.response_formatter import ApiResponse
from src.api.utils.s3_client import S3Client
import pandas as pd
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = S3Client()
MODEL_PATH = Path("/tmp/models/xgb_best_model.pkl")
TRAIN_FE_PATH = Path("/tmp/data/processed/feature_engineered_train.csv")

def lambda_handler(event, context):
    """
    Lambda handler for GET /health
    
    Returns:
    {
        "status": "healthy|unhealthy",
        "model_path": "...",
        "n_features_expected": 15,
        "aws_request_id": "...",
        "timestamp": "2025-01-10T..."
    }
    """
    try:
        logger.info(f"Health check invoked. Request ID: {context.aws_request_id}")
        
        status = {
            "model_path": str(MODEL_PATH),
            "aws_request_id": context.aws_request_id,
            "function_version": context.function_version,
            "memory_limit_mb": context.memory_limit_in_mb
        }
        
        # Check model
        if not MODEL_PATH.exists():
            logger.info("Model not found locally, downloading from S3")
            s3.download("models/xgb_best_model.pkl", str(MODEL_PATH))
        
        # Load feature schema
        if TRAIN_FE_PATH.exists():
            train_cols = pd.read_csv(TRAIN_FE_PATH, nrows=1)
            status["n_features_expected"] = len([c for c in train_cols.columns if c != "price"])
        else:
            logger.warning("Training data schema not found in Lambda environment")
            status["n_features_expected"] = None
        
        status["status"] = "healthy"
        logger.info("Health check passed")
        return ApiResponse.success(status)
    
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        status["status"] = "unhealthy"
        status["error"] = str(e)
        return ApiResponse.error(status, 503)
