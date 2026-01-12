#!/bin/bash
# Deploy script for Housing Prediction Lambda + API Gateway migration
# Supports CDK, Terraform, and SAM deployment methods

set -e

DEPLOYMENT_METHOD=${1:-cdk}
AWS_REGION=${2:-us-east-2}
ENVIRONMENT=${3:-prod}

echo "============================================"
echo "Housing Prediction API - Lambda Migration"
echo "============================================"
echo "Deployment Method: $DEPLOYMENT_METHOD"
echo "AWS Region: $AWS_REGION"
echo "Environment: $ENVIRONMENT"
echo ""

# ============================================
# Pre-deployment checks
# ============================================

echo "[1/5] Running pre-deployment checks..."

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first."
    exit 1
fi

# Verify AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Please configure AWS credentials."
    exit 1
fi

echo "✅ AWS CLI configured"

# ============================================
# Build Lambda layers and functions
# ============================================

echo ""
echo "[2/5] Building Lambda packages..."

mkdir -p build

# Build dependencies layer
echo "Building dependencies layer..."
mkdir -p build/lambda_layer_build/python
pip install -q -r pyproject.toml -t build/lambda_layer_build/python/ 2>/dev/null || true

# For production, use uv for better reproducibility
if command -v uv &> /dev/null; then
    uv pip install -q -r pyproject.toml --target build/lambda_layer_build/python/
fi

cd build/lambda_layer_build
zip -q -r ../dependencies_layer.zip . || true
cd ../..

echo "✅ Dependency layer built"

# ============================================
# Deployment based on method
# ============================================

case "$DEPLOYMENT_METHOD" in
    cdk)
        echo ""
        echo "[3/5] Installing CDK dependencies..."
        pip install -q aws-cdk-lib constructs
        
        echo ""
        echo "[4/5] Synthesizing CDK stack..."
        cd src/infrastructure/cdk
        cdk synth
        
        echo ""
        echo "[5/5] Deploying CDK stack..."
        cdk deploy --require-approval never
        cd ../../..
        
        echo ""
        echo "✅ CDK deployment complete"
        echo ""
        echo "API Endpoint: $(aws cloudformation describe-stacks \
            --stack-name HousingPredictionStack \
            --region $AWS_REGION \
            --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
            --output text)"
        ;;
    
    terraform)
        echo ""
        echo "[3/5] Initializing Terraform..."
        cd src/infrastructure/terraform
        terraform init
        
        # Create terraform.tfvars if not exists
        if [ ! -f terraform.tfvars ]; then
            cat > terraform.tfvars <<EOF
aws_region       = "$AWS_REGION"
s3_bucket_name   = "housing-regression-data-ajayr"
environment      = "$ENVIRONMENT"
EOF
        fi
        
        echo ""
        echo "[4/5] Planning Terraform deployment..."
        terraform plan -out=tfplan
        
        echo ""
        echo "[5/5] Applying Terraform configuration..."
        terraform apply tfplan
        
        echo ""
        echo "✅ Terraform deployment complete"
        echo ""
        echo "API Endpoint:"
        terraform output -raw api_endpoint
        
        cd ../../..
        ;;
    
    sam)
        echo ""
        echo "[3/5] Building SAM application..."
        sam build
        
        echo ""
        echo "[4/5] Packaging SAM application..."
        sam package \
            --output-template-file packaged.yaml \
            --s3-bucket housing-regression-data-ajayr \
            --region $AWS_REGION
        
        echo ""
        echo "[5/5] Deploying SAM application..."
        sam deploy \
            --template-file packaged.yaml \
            --stack-name housing-prediction-api-stack \
            --region $AWS_REGION \
            --capabilities CAPABILITY_IAM \
            --no-confirm-changeset
        
        echo ""
        echo "✅ SAM deployment complete"
        ;;
    
    *)
        echo "❌ Unknown deployment method: $DEPLOYMENT_METHOD"
        echo "Supported methods: cdk, terraform, sam"
        exit 1
        ;;
esac

echo ""
echo "============================================"
echo "Deployment successful!"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Verify API endpoints are responding"
echo "2. Update app.py with new API URL"
echo "3. Run validation tests"
echo "4. Monitor CloudWatch metrics"
echo ""
