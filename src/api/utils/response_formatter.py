import json
from typing import Any, Dict
import logging

logger = logging.getLogger()

class ApiResponse:
    """Format API responses for API Gateway."""
    
    @staticmethod
    def success(data: Any, status_code: int = 200) -> Dict:
        """
        Format successful API response for API Gateway (proxy integration).
        
        Args:
            data: Response payload (dict, list, etc.)
            status_code: HTTP status code (default: 200)
        
        Returns:
            Dict formatted for API Gateway proxy integration
        """
        logger.info(f"Returning success response with status {status_code}")
        return {
            "statusCode": status_code,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type,Authorization"
            },
            "body": json.dumps(data)
        }
    
    @staticmethod
    def error(error: Any, status_code: int = 400) -> Dict:
        """
        Format error API response for API Gateway (proxy integration).
        
        Args:
            error: Error message or object
            status_code: HTTP status code (default: 400)
        
        Returns:
            Dict formatted for API Gateway proxy integration
        """
        logger.error(f"Returning error response with status {status_code}: {error}")
        
        # Handle dict errors (from health check)
        if isinstance(error, dict):
            body = error
        else:
            body = {"error": str(error)}
        
        return {
            "statusCode": status_code,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type,Authorization"
            },
            "body": json.dumps(body)
        }
