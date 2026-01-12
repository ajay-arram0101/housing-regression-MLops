"""
Simplified Lambda handler for /predict endpoint.
Uses XGBoost native format and numpy (no pandas/joblib needed).
"""
import json
import os
import boto3
from pathlib import Path
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_BUCKET", "housing-regression-data-ajayr")
MODEL_PATH = Path("/tmp/model.xgb")
s3 = boto3.client("s3")

def download_model():
    """Download model from S3 if not cached."""
    if not MODEL_PATH.exists():
        logger.info(f"Downloading model from s3://{S3_BUCKET}/models/model.xgb")
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(S3_BUCKET, "models/model.xgb", str(MODEL_PATH))
    return MODEL_PATH

def lambda_handler(event, context):
    """
    Lambda handler for POST /predict
    Expects: {"body": "[{...features...}, ...]"}
    Returns: {"statusCode": 200, "body": {"predictions": [...]}}
    """
    try:
        logger.info(f"Predict handler invoked. Request ID: {context.aws_request_id}")
        
        # Parse request body
        body_str = event.get("body", "[]")
        if isinstance(body_str, str):
            records = json.loads(body_str)
        else:
            records = body_str
            
        if not records:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "No data provided"})
            }
        
        logger.info(f"Processing {len(records)} records")
        
        # Download and load model using XGBoost native format
        import xgboost as xgb
        import numpy as np
        
        model_path = download_model()
        booster = xgb.Booster()
        booster.load_model(str(model_path))
        
        # Expected feature columns in training order (from feature_engineered_train.csv)
        EXPECTED_FEATURES = [
            'year', 'quarter', 'month', 'median_list_price', 'median_ppsf', 
            'median_list_ppsf', 'homes_sold', 'pending_sales', 'new_listings', 
            'inventory', 'median_dom', 'avg_sale_to_list', 'sold_above_list', 
            'off_market_in_two_weeks', 'bank', 'bus', 'hospital', 'mall', 'park', 
            'restaurant', 'school', 'station', 'supermarket', 'Total Population', 
            'Median Age', 'Per Capita Income', 'Total Families Below Poverty', 
            'Total Housing Units', 'Median Rent', 'Median Home Value', 
            'Total Labor Force', 'Unemployed Population', 'Total School Age Population', 
            'Total School Enrollment', 'Median Commute Time', 'lat', 'lng', 
            'zipcode_freq', 'city_full_encoded'
        ]
        
        if records and isinstance(records[0], dict):
            # Store actuals if present
            actuals = [r.get("price") for r in records]
            actuals = [a for a in actuals if a is not None]
            actuals = actuals if actuals else None
            
            # Build feature matrix in exact training order
            X = np.array([
                [float(r.get(f, 0) or 0) for f in EXPECTED_FEATURES] 
                for r in records
            ], dtype=np.float32)
            
            # Replace any NaN with 0
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        else:
            X = np.array(records, dtype=np.float32)
            actuals = None
        
        # Make predictions with feature names
        dmatrix = xgb.DMatrix(X, feature_names=EXPECTED_FEATURES)
        predictions = booster.predict(dmatrix).tolist()
        
        response_body = {"predictions": predictions}
        if actuals:
            response_body["actuals"] = actuals
        
        logger.info(f"Generated {len(predictions)} predictions")
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": json.dumps(response_body)
        }
        
    except Exception as e:
        logger.error(f"Error in predict handler: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)})
        }
