import json
import pandas as pd
from pathlib import Path
from src.inference_pipeline.inference import predict
from src.api.utils.s3_client import S3Client
from src.api.utils.response_formatter import ApiResponse
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = S3Client()
MODEL_PATH = Path("/tmp/models/xgb_best_model.pkl")

def lambda_handler(event, context):
    """
    Lambda handler for POST /predict
    
    Event payload (API Gateway proxy integration):
    {
        "body": "[{...features...}, ...]",
        "headers": {...},
        "requestContext": {...}
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "predictions": [610759.06, 552594.31, ...],
            "actuals": [671509.91, 549957.59, ...] (optional)
        }
    }
    """
    try:
        logger.info(f"Predict handler invoked. Request ID: {context.aws_request_id}")
        
        # Parse request body
        body = json.loads(event.get("body", "[]"))
        if not body:
            return ApiResponse.error("No data provided", 400)
        
        logger.info(f"Processing {len(body)} records for prediction")
        
        # Prepare DataFrame
        df = pd.DataFrame(body)
        
        # Download model from S3 if not cached
        if not MODEL_PATH.exists():
            logger.info(f"Downloading model from S3 to {MODEL_PATH}")
            s3.download("models/xgb_best_model.pkl", str(MODEL_PATH))
        
        # Run inference
        preds_df = predict(df, model_path=MODEL_PATH)
        
        # Format response
        resp = {
            "predictions": preds_df["predicted_price"].astype(float).tolist()
        }
        if "actual_price" in preds_df.columns:
            resp["actuals"] = preds_df["actual_price"].astype(float).tolist()
        
        logger.info(f"Successfully generated {len(resp['predictions'])} predictions")
        return ApiResponse.success(resp)
    
    except Exception as e:
        logger.error(f"Error in predict handler: {str(e)}", exc_info=True)
        return ApiResponse.error(str(e), 500)
