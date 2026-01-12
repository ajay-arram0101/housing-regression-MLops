from aws_cdk import (
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_iam as iam,
    aws_s3 as s3,
    aws_logs as logs,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    core
)
from pathlib import Path
import json
import os

class HousingPredictionStack(core.Stack):
    """CDK Stack for Housing Prediction Lambda + API Gateway migration."""
    
    def __init__(self, scope: core.Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # Configuration
        s3_bucket_name = "housing-regression-data-ajayr"
        aws_region = "us-east-2"
        
        # ============================================
        # IAM Roles
        # ============================================
        
        lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for Housing Prediction Lambda functions"
        )
        
        # Attach basic execution policy
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )
        
        # S3 access
        s3_bucket = s3.Bucket.from_bucket_name(
            self, "DataBucket",
            bucket_name=s3_bucket_name
        )
        s3_bucket.grant_read_write(lambda_role)
        
        # ============================================
        # CloudWatch Logs
        # ============================================
        
        log_group = logs.LogGroup(
            self, "ApiLogs",
            log_group_name="/aws/lambda/housing-prediction-api",
            retention=logs.RetentionDays.ONE_MONTH
        )
        
        # ============================================
        # Lambda Layer with dependencies
        # ============================================
        
        layer = lambda_.LayerVersion(
            self, "SharedDependencies",
            code=lambda_.Code.from_asset(
                "src/lambda_layers/shared_dependencies",
                exclude=["*.pyc", "__pycache__", ".git"]
            ),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="Shared dependencies (numpy, pandas, sklearn, xgboost, boto3)"
        )
        
        # ============================================
        # Lambda Functions
        # ============================================
        
        predict_fn = self._create_function(
            self,
            "PredictFunction",
            handler="src.api.handlers.predict",
            memory_size=1024,
            timeout=core.Duration.seconds(30),
            layer=layer,
            role=lambda_role,
            environment={
                "S3_BUCKET": s3_bucket_name,
                "AWS_REGION": aws_region
            }
        )
        
        health_fn = self._create_function(
            self,
            "HealthFunction",
            handler="src.api.handlers.health",
            memory_size=256,
            timeout=core.Duration.seconds(10),
            layer=layer,
            role=lambda_role,
            environment={
                "S3_BUCKET": s3_bucket_name,
                "AWS_REGION": aws_region
            }
        )
        
        batch_fn = self._create_function(
            self,
            "BatchFunction",
            handler="src.api.handlers.batch",
            memory_size=2048,
            timeout=core.Duration.seconds(900),  # 15 minutes
            layer=layer,
            role=lambda_role,
            environment={
                "S3_BUCKET": s3_bucket_name,
                "AWS_REGION": aws_region
            }
        )
        
        predictions_fn = self._create_function(
            self,
            "PredictionsFunction",
            handler="src.api.handlers.predictions",
            memory_size=256,
            timeout=core.Duration.seconds(20),
            layer=layer,
            role=lambda_role,
            environment={
                "S3_BUCKET": s3_bucket_name,
                "AWS_REGION": aws_region
            }
        )
        
        # ============================================
        # API Gateway (REST API)
        # ============================================
        
        api = apigw.RestApi(
            self, "HousingPredictionApi",
            rest_api_name="housing-prediction-api",
            description="Housing Price Prediction API (Lambda Backend)",
            endpoint_types=[apigw.EndpointType.REGIONAL],
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                logging_level=apigw.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True,
                cache_cluster_enabled=False,
                throttle_settings=apigw.ThrottleSettings(
                    rate_limit=10000,
                    burst_limit=20000
                )
            )
        )
        
        # ============================================
        # API Routes
        # ============================================
        
        # GET /
        api.root.add_method(
            "GET",
            apigw.LambdaIntegration(health_fn),
            method_responses=[
                apigw.MethodResponse(status_code="200")
            ]
        )
        
        # POST /predict
        predict_resource = api.root.add_resource("predict")
        predict_resource.add_method(
            "POST",
            apigw.LambdaIntegration(predict_fn),
            method_responses=[
                apigw.MethodResponse(status_code="200"),
                apigw.MethodResponse(status_code="400"),
                apigw.MethodResponse(status_code="500")
            ]
        )
        
        # GET /health
        health_resource = api.root.add_resource("health")
        health_resource.add_method(
            "GET",
            apigw.LambdaIntegration(health_fn),
            method_responses=[
                apigw.MethodResponse(status_code="200"),
                apigw.MethodResponse(status_code="503")
            ]
        )
        
        # POST /run_batch
        batch_resource = api.root.add_resource("run_batch")
        batch_resource.add_method(
            "POST",
            apigw.LambdaIntegration(batch_fn),
            method_responses=[
                apigw.MethodResponse(status_code="200"),
                apigw.MethodResponse(status_code="500")
            ]
        )
        
        # GET /latest_predictions
        predictions_resource = api.root.add_resource("latest_predictions")
        predictions_resource.add_method(
            "GET",
            apigw.LambdaIntegration(predictions_fn),
            method_responses=[
                apigw.MethodResponse(status_code="200"),
                apigw.MethodResponse(status_code="404"),
                apigw.MethodResponse(status_code="500")
            ]
        )
        
        # ============================================
        # CloudWatch Alarms
        # ============================================
        
        # SNS Topic for alerts
        alert_topic = sns.Topic(
            self, "AlertTopic",
            display_name="Housing Prediction Lambda Alerts"
        )
        
        # Predict function error alarm
        predict_errors = cloudwatch.Alarm(
            self, "PredictErrorAlarm",
            metric=predict_fn.metric_errors(),
            threshold=10,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            alarm_description="Alert when predict function has errors"
        )
        predict_errors.add_alarm_action(cw_actions.SnsAction(alert_topic))
        
        # Predict function duration alarm
        predict_duration = cloudwatch.Alarm(
            self, "PredictDurationAlarm",
            metric=predict_fn.metric_duration(),
            statistic="Average",
            threshold=10000,  # 10 seconds
            evaluation_periods=1,
            alarm_description="Alert when predict function is slow"
        )
        predict_duration.add_alarm_action(cw_actions.SnsAction(alert_topic))
        
        # API Gateway errors
        api_errors = cloudwatch.Alarm(
            self, "ApiErrorAlarm",
            metric=api.metric_server_error_count(),
            threshold=100,
            evaluation_periods=1,
            alarm_description="Alert on high API error rate"
        )
        api_errors.add_alarm_action(cw_actions.SnsAction(alert_topic))
        
        # ============================================
        # Outputs
        # ============================================
        
        core.CfnOutput(
            self, "ApiUrl",
            value=api.url,
            description="API Gateway endpoint URL"
        )
        
        core.CfnOutput(
            self, "ApiId",
            value=api.rest_api_id,
            description="API Gateway ID"
        )
        
        core.CfnOutput(
            self, "PredictFunctionArn",
            value=predict_fn.function_arn,
            description="Predict Lambda function ARN"
        )
        
        core.CfnOutput(
            self, "HealthFunctionArn",
            value=health_fn.function_arn,
            description="Health check Lambda function ARN"
        )
        
        core.CfnOutput(
            self, "AlertTopicArn",
            value=alert_topic.topic_arn,
            description="SNS Topic for alerts"
        )
    
    @staticmethod
    def _create_function(
        scope,
        name: str,
        handler: str,
        memory_size: int,
        timeout: core.Duration,
        layer: lambda_.LayerVersion,
        role: iam.Role,
        environment: dict
    ) -> lambda_.Function:
        """
        Helper to create Lambda function with common config.
        
        Args:
            scope: CDK construct scope
            name: Logical ID
            handler: Handler module path (e.g., 'src.api.handlers.predict')
            memory_size: Memory in MB
            timeout: Function timeout
            layer: Lambda layer to attach
            role: IAM role
            environment: Environment variables
        
        Returns:
            Lambda function construct
        """
        return lambda_.Function(
            scope, name,
            code=lambda_.Code.from_asset(
                ".",
                exclude=["*.git", "__pycache__", "*.pyc", ".pytest_cache", "node_modules"]
            ),
            handler=f"{handler}.lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            memory_size=memory_size,
            timeout=timeout,
            layers=[layer],
            role=role,
            environment=environment,
            description=f"Housing Prediction - {name}",
            ephemeral_storage=core.Size.mebibytes(512),
            tracing=lambda_.Tracing.ACTIVE  # Enable X-Ray tracing
        )
