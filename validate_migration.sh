#!/bin/bash
# Validation script for migration
# Tests API endpoints and verifies functionality

set -e

API_ENDPOINT=${1:-""}
OLD_API_URL=${2:-"http://housing-api-alb-209669040.us-east-2.elb.amazonaws.com:8000"}

if [ -z "$API_ENDPOINT" ]; then
    echo "Usage: $0 <api-endpoint> [old-api-url]"
    echo "Example: $0 https://abc123.execute-api.us-east-2.amazonaws.com/prod"
    exit 1
fi

echo "============================================"
echo "Migration Validation Tests"
echo "============================================"
echo "New API: $API_ENDPOINT"
echo "Old API: $OLD_API_URL"
echo ""

PASS=0
FAIL=0

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local data=$4
    
    echo -n "Testing $name... "
    
    if [ "$method" = "POST" ]; then
        response=$(curl -s -X POST "$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data" \
            -w "\n%{http_code}")
    else
        response=$(curl -s -X GET "$endpoint" \
            -w "\n%{http_code}")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 201 ]; then
        echo -e "${GREEN}✅ PASS${NC} (HTTP $http_code)"
        PASS=$((PASS+1))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC} (HTTP $http_code)"
        echo "Response: $body"
        FAIL=$((FAIL+1))
        return 1
    fi
}

# ============================================
# Test new API endpoints
# ============================================

echo "[New API - Lambda]"
echo ""

test_endpoint "GET /" "GET" "$API_ENDPOINT/" ""
test_endpoint "GET /health" "GET" "$API_ENDPOINT/health" ""

# Test predict with sample data
SAMPLE_DATA='[{"feature1": 1.0, "feature2": 2.0}]'
test_endpoint "POST /predict" "POST" "$API_ENDPOINT/predict" "$SAMPLE_DATA"

test_endpoint "GET /latest_predictions" "GET" "$API_ENDPOINT/latest_predictions?limit=5" ""

echo ""
echo "[Old API - ECS (for comparison)]"
echo ""

test_endpoint "GET /health (ECS)" "GET" "$OLD_API_URL/health" "" || true

echo ""
echo "============================================"
echo "Validation Results"
echo "============================================"
echo -e "Passed: ${GREEN}$PASS${NC}"
echo -e "Failed: ${RED}$FAIL${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi
