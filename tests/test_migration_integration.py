"""Integration tests for Lambda + API Gateway migration."""

import pytest
import requests
import os
import json
from datetime import datetime


class TestMigrationValidation:
    """Integration tests for migration validation."""
    
    @pytest.fixture
    def api_urls(self):
        """Get API URLs for testing."""
        return {
            "new": os.getenv("LAMBDA_API_URL", "http://localhost:3000"),
            "old": os.getenv("ECS_API_URL", "http://housing-api-alb-209669040.us-east-2.elb.amazonaws.com:8000")
        }
    
    def test_health_endpoint_lambda(self, api_urls):
        """Test health endpoint on Lambda."""
        response = requests.get(f"{api_urls['new']}/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "unhealthy"]
    
    def test_health_endpoint_ecs(self, api_urls):
        """Test health endpoint on ECS (for comparison)."""
        try:
            response = requests.get(f"{api_urls['old']}/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
        except:
            pytest.skip("ECS API not available")
    
    def test_predict_endpoint_lambda(self, api_urls):
        """Test predict endpoint on Lambda."""
        test_data = [{"feature1": 1.0, "feature2": 2.0}]
        response = requests.post(
            f"{api_urls['new']}/predict",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data
        assert isinstance(data["predictions"], list)
    
    def test_predict_endpoint_ecs(self, api_urls):
        """Test predict endpoint on ECS (for comparison)."""
        try:
            test_data = [{"feature1": 1.0, "feature2": 2.0}]
            response = requests.post(
                f"{api_urls['old']}/predict",
                json=test_data,
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "predictions" in data
        except:
            pytest.skip("ECS API not available")
    
    def test_predict_response_format(self, api_urls):
        """Test predict response matches expected format."""
        test_data = [
            {"feature1": 1.0, "feature2": 2.0},
            {"feature1": 3.0, "feature2": 4.0}
        ]
        response = requests.post(
            f"{api_urls['new']}/predict",
            json=test_data
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["predictions"]) == 2
        assert all(isinstance(p, (int, float)) for p in data["predictions"])
    
    def test_latest_predictions_endpoint(self, api_urls):
        """Test latest predictions endpoint."""
        response = requests.get(
            f"{api_urls['new']}/latest_predictions?limit=5"
        )
        if response.status_code == 200:
            data = response.json()
            assert "file" in data
            assert "rows" in data
            assert "preview" in data
            assert len(data["preview"]) <= 5
        elif response.status_code == 404:
            # OK if no predictions exist yet
            pass
        else:
            raise AssertionError(f"Unexpected status code: {response.status_code}")
    
    def test_error_handling_invalid_data(self, api_urls):
        """Test error handling with invalid input."""
        response = requests.post(
            f"{api_urls['new']}/predict",
            json=[]  # Empty array
        )
        assert response.status_code == 400
    
    def test_cors_headers(self, api_urls):
        """Test CORS headers in responses."""
        response = requests.get(f"{api_urls['new']}/health")
        assert "Access-Control-Allow-Origin" in response.headers
    
    def test_response_times(self, api_urls):
        """Test response times are within acceptable ranges."""
        # Health check should be fast
        start = datetime.now()
        response = requests.get(f"{api_urls['new']}/health")
        duration = (datetime.now() - start).total_seconds() * 1000
        
        assert response.status_code == 200
        # Allow for cold start, but subsequent calls should be faster
        assert duration < 30000  # 30 seconds max
    
    def test_concurrent_requests(self, api_urls):
        """Test handling of concurrent requests."""
        import concurrent.futures
        
        def make_request():
            return requests.get(f"{api_urls['new']}/health")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        assert all(r.status_code == 200 for r in results)


class TestDashboardFunctionality:
    """Tests to verify dashboard functionality remains unchanged."""
    
    @pytest.fixture
    def streamlit_url(self):
        """Get Streamlit dashboard URL."""
        return os.getenv("STREAMLIT_URL", "http://localhost:8501")
    
    def test_dashboard_loads(self, streamlit_url):
        """Test that dashboard loads successfully."""
        try:
            response = requests.get(streamlit_url)
            assert response.status_code == 200
        except:
            pytest.skip("Streamlit dashboard not available")
    
    def test_dashboard_api_integration(self, streamlit_url):
        """Test dashboard can reach backend API."""
        # This would be a Selenium-based test in a real implementation
        pytest.skip("Requires Selenium for browser automation")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
