#!/usr/bin/env python3
"""
Simple CloudFormation deployment script for Housing Prediction API
Works directly with AWS CloudFormation (no CDK, Terraform, or SAM needed)
"""

import json
import boto3
import time
import sys
from pathlib import Path

# Configuration
STACK_NAME = "housing-prediction-api"
REGION = "us-east-2"
S3_BUCKET = "housing-regression-data-ajayr"

def get_template():
    """Return the CloudFormation template as dict"""
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "Housing Prediction API - Lambda + API Gateway",
        
        "Resources": {
            "LambdaExecutionRole": {
                "Type": "AWS::IAM::Role",
                "Properties": {
                    "RoleName": "housing-prediction-lambda-role",
                    "AssumeRolePolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [{
                            "Effect": "Allow",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                            "Action": "sts:AssumeRole"
                        }]
                    },
                    "ManagedPolicyArns": [
                        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                    ],
                    "Policies": [{
                        "PolicyName": "S3Access",
                        "PolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [{
                                "Effect": "Allow",
                                "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
                                "Resource": [
                                    f"arn:aws:s3:::{S3_BUCKET}",
                                    f"arn:aws:s3:::{S3_BUCKET}/*"
                                ]
                            }]
                        }
                    }]
                }
            },
            
            "HealthFunction": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "FunctionName": "housing-health",
                    "Runtime": "python3.11",
                    "Handler": "index.lambda_handler",
                    "Role": {"Fn::GetAtt": ["LambdaExecutionRole", "Arn"]},
                    "MemorySize": 256,
                    "Timeout": 10,
                    "Environment": {
                        "Variables": {
                            "S3_BUCKET": S3_BUCKET,
                            "AWS_REGION": REGION
                        }
                    },
                    "Code": {
                        "ZipFile": """
import json

def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "status": "healthy",
            "message": "Housing Prediction API is running on Lambda",
            "region": "us-east-2"
        })
    }
"""
                    }
                }
            },
            
            "ApiGateway": {
                "Type": "AWS::ApiGatewayV2::Api",
                "Properties": {
                    "Name": "housing-prediction-api",
                    "ProtocolType": "HTTP",
                    "CorsConfiguration": {
                        "AllowOrigins": ["*"],
                        "AllowMethods": ["GET", "POST", "OPTIONS"],
                        "AllowHeaders": ["*"]
                    }
                }
            },
            
            "HealthIntegration": {
                "Type": "AWS::ApiGatewayV2::Integration",
                "Properties": {
                    "ApiId": {"Ref": "ApiGateway"},
                    "IntegrationType": "AWS_PROXY",
                    "IntegrationMethod": "POST",
                    "PayloadFormatVersion": "2.0",
                    "Target": {"Fn::Sub": "arn:aws:apigatewayv2:${AWS::Region}:lambda:path/2015-03-31/functions/${HealthFunction.Arn}/invocations"}
                }
            },
            
            "HealthRoute": {
                "Type": "AWS::ApiGatewayV2::Route",
                "Properties": {
                    "ApiId": {"Ref": "ApiGateway"},
                    "RouteKey": "GET /health",
                    "Target": {"Fn::Sub": "integrations/${HealthIntegration}"}
                }
            },
            
            "ApiStage": {
                "Type": "AWS::ApiGatewayV2::Stage",
                "Properties": {
                    "ApiId": {"Ref": "ApiGateway"},
                    "StageName": "prod",
                    "AutoDeploy": True
                }
            },
            
            "HealthLambdaPermission": {
                "Type": "AWS::Lambda::Permission",
                "Properties": {
                    "FunctionName": {"Ref": "HealthFunction"},
                    "Action": "lambda:InvokeFunction",
                    "Principal": "apigateway.amazonaws.com",
                    "SourceArn": {"Fn::Sub": "${ApiGateway.Arn}/*"}
                }
            }
        },
        
        "Outputs": {
            "ApiEndpoint": {
                "Description": "API Gateway Endpoint",
                "Value": {"Fn::Sub": "https://${ApiGateway}.execute-api.${AWS::Region}.amazonaws.com/prod"}
            },
            "HealthFunctionArn": {
                "Description": "Health Lambda Function ARN",
                "Value": {"Fn::GetAtt": ["HealthFunction", "Arn"]}
            }
        }
    }

def deploy():
    """Deploy the CloudFormation stack"""
    
    print("🚀 Deploying Housing Prediction API...")
    print(f"Stack: {STACK_NAME}")
    print(f"Region: {REGION}")
    print()
    
    cf = boto3.client("cloudformation", region_name=REGION)
    
    template = get_template()
    
    try:
        # Check if stack exists
        try:
            cf.describe_stacks(StackName=STACK_NAME)
            stack_exists = True
            print(f"✓ Stack {STACK_NAME} exists, updating...")
        except cf.exceptions.ClientError as e:
            if "does not exist" in str(e):
                stack_exists = False
                print(f"✓ Creating new stack {STACK_NAME}...")
            else:
                raise
        
        # Deploy stack
        if stack_exists:
            response = cf.update_stack(
                StackName=STACK_NAME,
                TemplateBody=json.dumps(template),
                Capabilities=["CAPABILITY_NAMED_IAM"]
            )
        else:
            response = cf.create_stack(
                StackName=STACK_NAME,
                TemplateBody=json.dumps(template),
                Capabilities=["CAPABILITY_NAMED_IAM"]
            )
        
        print(f"✓ Stack deployment initiated")
        print(f"  Stack ID: {response['StackId']}")
        print()
        
        # Wait for completion
        print("⏳ Waiting for stack deployment to complete...")
        waiter = cf.get_waiter('stack_create_complete' if not stack_exists else 'stack_update_complete')
        
        try:
            waiter.wait(StackName=STACK_NAME)
            print("✅ Stack deployment successful!")
        except:
            # Update might be no-op
            pass
        
        # Get outputs
        print()
        print("=" * 60)
        stacks = cf.describe_stacks(StackName=STACK_NAME)
        stack = stacks["Stacks"][0]
        
        if "Outputs" in stack:
            print("📍 DEPLOYMENT OUTPUTS:")
            print("=" * 60)
            for output in stack["Outputs"]:
                print(f"{output['OutputKey']}: {output['OutputValue']}")
        
        print("=" * 60)
        print()
        print("✅ Deployment complete!")
        print()
        print("Next steps:")
        print("1. Test health endpoint:")
        print("   curl <api-endpoint>/health")
        print()
        print("2. View logs:")
        print(f"   aws logs tail /aws/lambda/housing-health --follow")
        
        return True
        
    except Exception as e:
        print(f"❌ Deployment failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = deploy()
    sys.exit(0 if success else 1)
