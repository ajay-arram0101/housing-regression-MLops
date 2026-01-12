from src.batch.run_monthly import run_monthly_predictions
from src.api.utils.response_formatter import ApiResponse
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda handler for POST /run_batch
    
    Triggers monthly batch prediction processing.
    
    Returns:
    {
        "status": "success|error",
        "rows_predicted": 1000,
        "output_dir": "data/predictions/",
        "execution_time_ms": 5000,
        "timestamp": "2025-01-10T..."
    }
    """
    try:
        start_time = datetime.utcnow()
        logger.info(f"Batch processing started. Request ID: {context.aws_request_id}")
        
        preds = run_monthly_predictions()
        
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.info(f"Batch processing completed. {len(preds)} rows predicted in {execution_time:.0f}ms")
        
        return ApiResponse.success({
            "status": "success",
            "rows_predicted": len(preds),
            "output_dir": "data/predictions/",
            "execution_time_ms": execution_time,
            "timestamp": start_time.isoformat()
        })
    
    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}", exc_info=True)
        return ApiResponse.error(str(e), 500)
