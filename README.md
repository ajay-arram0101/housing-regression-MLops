# Housing Price Prediction - ML Pipeline

Predicts US metropolitan housing prices using XGBoost regression.

Link : https://nqhku2ro67.execute-api.us-east-2.amazonaws.com/prod/dashboard

## ML Pipeline

| Stage | Description |
|-------|-------------|
| Data Split | Train/Test/Eval split with time-based validation |
| EDA & Cleaning | Handle missing values, outliers, data quality checks |
| Feature Engineering | Date features, regional encodings, lag features |
| Baseline | Simple mean/median models for comparison |
| Linear Models | Ridge, Lasso, ElasticNet with regularization |
| XGBoost | Gradient boosting with hyperparameter tuning |
| MLflow | Experiment tracking, model versioning, metrics logging |

## Model

- **Algorithm**: XGBoost Regressor
- **Target**: Housing price index
- **Features**: 15 engineered features (temporal, regional, economic)
- **Metrics**: RMSE, MAE, R²

## Deployment Architecture

```
User Request → API Gateway → Lambda → S3 (model + data)
                                ↓
                          XGBoost Inference
                                ↓
                          JSON Response
```

## AWS Services

| Service | Purpose |
|---------|---------|
| Lambda | Inference (housing-predict), Dashboard (housing-dashboard), Health check |
| API Gateway | REST API endpoints |
| S3 | Model storage, training data, predictions |
| Lambda Layer | XGBoost, NumPy, SciPy |
| CloudWatch | Logs, metrics, monitoring |

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/predict` | POST | Single prediction |
| `/health` | GET | Health check |
| `/dashboard` | GET | Browser UI with charts |

## Project Structure

```
├── notebooks/          # Jupyter notebooks
├── src/
│   ├── feature_pipeline/   # Data processing
│   ├── training_pipeline/  # Model training
│   └── inference_pipeline/ # Prediction logic
├── lambda_handlers/    # AWS Lambda functions
├── models/             # Trained models
├── data/
│   ├── raw/            # Original datasets
│   └── processed/      # Feature engineered data
├── configs/            # App, MLflow, expectations configs
└── tests/              # Unit and integration tests
```

## Run Locally

```bash
# Install dependencies
pip install -e .

# Train model
python -m src.training_pipeline.train

# Run API locally
uvicorn app:app --reload
```

## Deploy to AWS

```bash
# Package and deploy Lambda
zip -r lambda.zip lambda_handlers/
aws lambda update-function-code --function-name housing-predict --zip-file fileb://lambda.zip
```

## Tech Stack

- Python 3.11
- XGBoost
- MLflow
- FastAPI (local)
- AWS Lambda + API Gateway (production)
- Streamlit (optional dashboard)
