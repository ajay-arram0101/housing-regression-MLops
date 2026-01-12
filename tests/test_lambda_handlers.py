"""Tests for Lambda handlers."""

import pytest
import json
from unittest.mock import MagicMock, patch
from src.api.handlers import predict, health, batch, predictions
from src.api.utils.response_formatter import ApiResponse


class TestPredictHandler:
    """Tests for predict Lambda handler."""
    
    def test_predict_handler_valid_input(self):
        """Test predict handler with valid input."""
        event = {
            "body": json.dumps([{"feature1": 1.0, "feature2": 2.0}])
        }
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        
        # Mock the predict function
        with patch("src.api.handlers.predict.predict") as mock_predict:
            mock_df = MagicMock()
            mock_df["predicted_price"] = [610759.06]
            mock_predict.return_value = mock_df
            
            # Mock MODEL_PATH.exists()
            with patch("src.api.handlers.predict.MODEL_PATH.exists", return_value=True):
                response = predict.lambda_handler(event, context)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "predictions" in body
    
    def test_predict_handler_empty_input(self):
        """Test predict handler with empty input."""
        event = {"body": "[]"}
        context = MagicMock()
        
        response = predict.lambda_handler(event, context)
        
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
    
    def test_predict_handler_invalid_json(self):
        """Test predict handler with invalid JSON."""
        event = {"body": "invalid json"}
        context = MagicMock()
        
        response = predict.lambda_handler(event, context)
        
        assert response["statusCode"] == 500


class TestHealthHandler:
    """Tests for health check Lambda handler."""
    
    def test_health_handler_healthy(self):
        """Test health handler when model is available."""
        event = {}
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        context.function_version = "$LATEST"
        context.memory_limit_in_mb = 256
        
        with patch("src.api.handlers.health.MODEL_PATH.exists", return_value=True):
            with patch("src.api.handlers.health.TRAIN_FE_PATH.exists", return_value=True):
                with patch("pandas.read_csv") as mock_read:
                    mock_read.return_value = MagicMock(columns=["feature1", "feature2", "price"])
                    response = health.lambda_handler(event, context)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "healthy"
        assert "aws_request_id" in body
    
    def test_health_handler_model_not_found(self):
        """Test health handler when model is missing."""
        event = {}
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        
        with patch("src.api.handlers.health.MODEL_PATH.exists", return_value=False):
            with patch("src.api.handlers.health.s3.download", side_effect=Exception("S3 error")):
                response = health.lambda_handler(event, context)
        
        assert response["statusCode"] == 503
        body = json.loads(response["body"])
        assert body["status"] == "unhealthy"


class TestBatchHandler:
    """Tests for batch processing Lambda handler."""
    
    def test_batch_handler_success(self):
        """Test batch handler successful execution."""
        event = {}
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        context.get_remaining_time_in_millis = MagicMock(return_value=890000)
        
        with patch("src.api.handlers.batch.run_monthly_predictions") as mock_batch:
            mock_batch.return_value = MagicMock(__len__=lambda x: 1000)
            response = batch.lambda_handler(event, context)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert body["rows_predicted"] == 1000


class TestPredictionsHandler:
    """Tests for predictions retrieval Lambda handler."""
    
    def test_predictions_handler_success(self):
        """Test predictions handler with valid data."""
        event = {
            "queryStringParameters": {"limit": "5"}
        }
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        
        with patch("pathlib.Path.glob") as mock_glob:
            mock_file = MagicMock()
            mock_file.name = "preds_2025-01-10.csv"
            mock_glob.return_value = [mock_file]
            
            with patch("pandas.read_csv") as mock_read:
                mock_df = MagicMock()
                mock_df.head = MagicMock(return_value=MagicMock(to_dict=MagicMock(return_value=[])))
                mock_df.__len__ = lambda x: 1000
                mock_read.return_value = mock_df
                
                response = predictions.lambda_handler(event, context)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "file" in body
        assert "rows" in body
    
    def test_predictions_handler_no_files(self):
        """Test predictions handler when no files exist."""
        event = {"queryStringParameters": None}
        context = MagicMock()
        
        with patch("pathlib.Path.glob") as mock_glob:
            mock_glob.return_value = []
            response = predictions.lambda_handler(event, context)
        
        assert response["statusCode"] == 404


class TestResponseFormatter:
    """Tests for response formatting utility."""
    
    def test_success_response(self):
        """Test success response formatting."""
        data = {"key": "value"}
        response = ApiResponse.success(data)
        
        assert response["statusCode"] == 200
        assert "headers" in response
        assert response["headers"]["Content-Type"] == "application/json"
        assert json.loads(response["body"]) == data
    
    def test_error_response(self):
        """Test error response formatting."""
        response = ApiResponse.error("Test error", 400)
        
        assert response["statusCode"] == 400
        assert "headers" in response
        body = json.loads(response["body"])
        assert body["error"] == "Test error"
    
    def test_cors_headers(self):
        """Test CORS headers in response."""
        response = ApiResponse.success({})
        
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"
        assert "Access-Control-Allow-Methods" in response["headers"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
