#!/usr/bin/env python3
"""CDK App for Housing Prediction API."""

from aws_cdk import core
from stack import HousingPredictionStack

app = core.App()

HousingPredictionStack(
    app, "HousingPredictionStack",
    env=core.Environment(
        account="261899902410",
        region="us-east-2"
    ),
    description="Housing Price Prediction API migrated to Lambda + API Gateway"
)

app.synth()
