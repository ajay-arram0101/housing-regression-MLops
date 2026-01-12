from pathlib import Path
from src.api.utils.response_formatter import ApiResponse
import pandas as pd
import logging
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda handler for GET /latest_predictions?limit=5
    
    Retrieves the most recent batch predictions.
    
    Query Parameters:
    - limit (int): Number of rows to return (default: 5)
    
    Returns:
    {
        "file": "preds_2025-01-10.csv",
        "rows": 1000,
        "preview": [
            {"date": "2025-01-10", "region": "...", "actual_price": ..., "prediction": ...},
            ...
        ]
    }
    """
    try:
        logger.info(f"Latest predictions handler invoked. Request ID: {context.aws_request_id}")
        
        # Parse query parameters
        query_params = event.get("queryStringParameters") or {}
        limit = int(query_params.get("limit", 5))
        
        logger.info(f"Retrieving latest {limit} predictions")
        
        pred_dir = Path("data/predictions")
        files = sorted(pred_dir.glob("preds_*.csv"))
        
        if not files:
            logger.warning("No prediction files found")
            return ApiResponse.error("No predictions found", 404)
        
        latest_file = files[-1]
        logger.info(f"Reading latest file: {latest_file.name}")
        
        df = pd.read_csv(latest_file)
        
        preview = df.head(limit).to_dict(orient="records")
        # Convert any NaN to None for JSON serialization
        preview = json.loads(json.dumps(preview, default=str))
        
        logger.info(f"Returning {len(preview)} rows from {latest_file.name}")
        
        return ApiResponse.success({
            "file": latest_file.name,
            "rows": len(df),
            "preview": preview
        })
    
    except Exception as e:
        logger.error(f"Error retrieving predictions: {str(e)}", exc_info=True)
        return ApiResponse.error(str(e), 500)
