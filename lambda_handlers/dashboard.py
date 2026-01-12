"""
OPTIMIZED Lambda handler for browser-based prediction dashboard.
Key optimizations:
1. Global caching of model, data, and parsed CSV
2. Lazy loading - only download/parse once
3. Pre-compute dropdown options
"""
import json
import os
import boto3
from pathlib import Path
from urllib.parse import parse_qs
import logging
import time

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_BUCKET", "housing-regression-data-ajayr")
MODEL_PATH = Path("/tmp/model.xgb")
DATA_PATH = Path("/tmp/feature_engineered_test.csv")
META_PATH = Path("/tmp/cleaning_test.csv")
s3 = boto3.client("s3")

# ============================================================
# GLOBAL CACHE - Persists across warm invocations
# ============================================================
CACHE = {
    "model": None,
    "fe_data": None,
    "meta_data": None,
    "years": None,
    "regions": None,
    "initialized": False
}

EXPECTED_FEATURES = [
    'year', 'quarter', 'month', 'median_list_price', 'median_ppsf', 
    'median_list_ppsf', 'homes_sold', 'pending_sales', 'new_listings', 
    'inventory', 'median_dom', 'avg_sale_to_list', 'sold_above_list', 
    'off_market_in_two_weeks', 'bank', 'bus', 'hospital', 'mall', 'park', 
    'restaurant', 'school', 'station', 'supermarket', 'Total Population', 
    'Median Age', 'Per Capita Income', 'Total Families Below Poverty', 
    'Total Housing Units', 'Median Rent', 'Median Home Value', 
    'Total Labor Force', 'Unemployed Population', 'Total School Age Population', 
    'Total School Enrollment', 'Median Commute Time', 'lat', 'lng', 
    'zipcode_freq', 'city_full_encoded'
]

def download_file(s3_key, local_path):
    """Download file from S3 if not cached."""
    if not local_path.exists():
        logger.info(f"Downloading {s3_key} from S3")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(S3_BUCKET, s3_key, str(local_path))
    return local_path

def parse_csv_fast(path):
    """Fast CSV parsing with type inference."""
    with open(path, 'r') as f:
        lines = f.readlines()
    
    headers = lines[0].strip().split(',')
    data = []
    
    for line in lines[1:]:
        values = line.strip().split(',')
        row = {}
        for i, h in enumerate(headers):
            if i < len(values):
                val = values[i]
                try:
                    row[h] = float(val) if val else 0.0
                except:
                    row[h] = val
            else:
                row[h] = 0.0
        data.append(row)
    
    return headers, data

def initialize_cache():
    """Initialize global cache once per Lambda container."""
    global CACHE
    
    if CACHE["initialized"]:
        logger.info("Using cached data (warm invocation)")
        return
    
    start = time.time()
    logger.info("Initializing cache (cold start)...")
    
    import numpy as np
    import xgboost as xgb
    
    # Download files
    download_file("models/model.xgb", MODEL_PATH)
    download_file("processed/feature_engineered_test.csv", DATA_PATH)
    download_file("processed/cleaning_test.csv", META_PATH)
    
    # Load model
    CACHE["model"] = xgb.Booster()
    CACHE["model"].load_model(str(MODEL_PATH))
    logger.info(f"Model loaded in {time.time() - start:.2f}s")
    
    # Parse CSVs
    _, CACHE["fe_data"] = parse_csv_fast(DATA_PATH)
    _, CACHE["meta_data"] = parse_csv_fast(META_PATH)
    logger.info(f"CSV parsed in {time.time() - start:.2f}s")
    
    # Pre-compute dropdown options
    CACHE["years"] = sorted(set(int(r.get('year', 2022)) for r in CACHE["fe_data"]))
    CACHE["regions"] = sorted(set(str(r.get('city_full', '')) for r in CACHE["meta_data"] if r.get('city_full')))[:50]
    
    CACHE["initialized"] = True
    logger.info(f"Cache initialized in {time.time() - start:.2f}s total")

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Housing Price Prediction - Explorer</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #fff; color: #000; }}
        h1 {{ color: #000; border-bottom: 2px solid #000; padding-bottom: 10px; font-weight: bold; }}
        .form-container {{ background: #fafafa; padding: 20px; border: 1px solid #000; margin-bottom: 20px; }}
        .form-row {{ display: flex; gap: 20px; margin-bottom: 15px; }}
        .form-group {{ flex: 1; }}
        label {{ display: block; font-weight: bold; margin-bottom: 5px; color: #000; }}
        select {{ width: 100%; padding: 10px; border: 2px solid #000; font-size: 14px; color: #000; background: #fff; }}
        button {{ background: #fff; color: #000; padding: 12px 30px; border: 2px solid #000; cursor: pointer; font-size: 16px; font-weight: bold; }}
        button:hover {{ background: #f0f0f0; }}
        .status {{ background: #f0f0f0; padding: 10px 15px; margin-bottom: 20px; color: #000; border-left: 4px solid #000; }}
        table {{ width: 100%; border-collapse: collapse; background: white; }}
        th {{ background: #000; color: white; padding: 12px; text-align: left; font-weight: bold; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid #000; color: #000; }}
        tr:hover {{ background: #f0f0f0; }}
        .metrics {{ display: flex; gap: 20px; margin: 20px 0; }}
        .metric {{ background: #fafafa; padding: 15px 25px; border: 2px solid #000; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #000; }}
        .metric-label {{ color: #000; font-size: 12px; font-weight: bold; }}
        .info {{ background: #f5f5f5; padding: 15px; color: #000; margin-top: 20px; border-left: 4px solid #000; }}
        h3 {{ color: #000; margin-top: 30px; font-weight: bold; }}
        .perf {{ font-size: 11px; color: #666; margin-top: 10px; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <h1>Housing Price Prediction - Explorer</h1>
    
    <div class="form-container">
        <form method="GET">
            <div class="form-row">
                <div class="form-group">
                    <label>Select Year</label>
                    <select name="year">
                        {year_options}
                    </select>
                </div>
                <div class="form-group">
                    <label>Select Month</label>
                    <select name="month">
                        {month_options}
                    </select>
                </div>
                <div class="form-group">
                    <label>Select Region</label>
                    <select name="region">
                        {region_options}
                    </select>
                </div>
            </div>
            <button type="submit">Show Predictions</button>
        </form>
    </div>
    
    {results_html}
    
    <div class="perf">Processing time: {processing_time}ms</div>
</body>
</html>
'''

def lambda_handler(event, context):
    """Handle GET requests to show prediction dashboard."""
    start_time = time.time()
    
    try:
        import numpy as np
        import xgboost as xgb
        
        # Initialize cache (fast on warm invocations)
        initialize_cache()
        
        init_time = int((time.time() - start_time) * 1000)
        
        # Get cached data
        model = CACHE["model"]
        fe_data = CACHE["fe_data"]
        meta_data = CACHE["meta_data"]
        years = CACHE["years"]
        regions = CACHE["regions"]
        
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        selected_year = int(query_params.get('year', years[0] if years else 2022))
        selected_month = int(query_params.get('month', 1))
        selected_region = query_params.get('region', 'All')
        
        # Build dropdown options
        year_options = ''.join(f'<option value="{y}" {"selected" if y == selected_year else ""}>{y}</option>' for y in years)
        month_options = ''.join(f'<option value="{m}" {"selected" if m == selected_month else ""}>{m}</option>' for m in range(1, 13))
        region_options = '<option value="All">All</option>' + ''.join(
            f'<option value="{r}" {"selected" if r == selected_region else ""}>{r}</option>' for r in regions
        )
        
        results_html = '<div class="info">Choose filters and click <strong>Show Predictions</strong> to compute.</div>'
        
        # If we have query params, run predictions
        if query_params:
            filter_start = time.time()
            
            # Filter data (optimized - single pass)
            filtered_indices = []
            for i in range(min(len(fe_data), len(meta_data))):
                fe_row = fe_data[i]
                meta_row = meta_data[i]
                
                row_year = int(fe_row.get('year', 0))
                row_month = int(fe_row.get('month', 0))
                row_region = str(meta_row.get('city_full', ''))
                
                if row_year == selected_year and row_month == selected_month:
                    if selected_region == 'All' or row_region == selected_region:
                        filtered_indices.append(i)
                        if len(filtered_indices) >= 10:  # Limit early
                            break
            
            filter_time = int((time.time() - filter_start) * 1000)
            
            if not filtered_indices:
                results_html = '<div class="info">No data found for these filters.</div>'
            else:
                predict_start = time.time()
                
                # Build feature matrix
                X = []
                actuals = []
                dates = []
                regions_list = []
                
                for idx in filtered_indices:
                    row = fe_data[idx]
                    meta_row = meta_data[idx]
                    features = [float(row.get(f, 0) or 0) for f in EXPECTED_FEATURES]
                    X.append(features)
                    actuals.append(float(row.get('price', 0)))
                    dates.append(str(meta_row.get('date', 'N/A')))
                    regions_list.append(str(meta_row.get('city_full', 'N/A')))
                
                X = np.array(X, dtype=np.float32)
                X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
                
                dmatrix = xgb.DMatrix(X, feature_names=EXPECTED_FEATURES)
                predictions = model.predict(dmatrix).tolist()
                
                predict_time = int((time.time() - predict_start) * 1000)
                
                # Calculate metrics
                errors = [abs(p - a) for p, a in zip(predictions, actuals)]
                mae = sum(errors) / len(errors) if errors else 0
                pct_errors = [(abs(p - a) / a * 100) if a > 0 else 0 for p, a in zip(predictions, actuals)]
                avg_pct_error = sum(pct_errors) / len(pct_errors) if pct_errors else 0
                avg_prediction = sum(predictions) / len(predictions) if predictions else 0
                avg_actual = sum(actuals) / len(actuals) if actuals else 0
                
                # Build table rows
                table_rows = ''
                for i, (date, region, actual, pred) in enumerate(zip(dates, regions_list, actuals, predictions)):
                    error = abs(pred - actual)
                    pct_error = (error / actual * 100) if actual > 0 else 0
                    table_rows += f'''
                    <tr>
                        <td>{i+1}</td>
                        <td>{date}</td>
                        <td>{region}</td>
                        <td>${actual:,.2f}</td>
                        <td>${pred:,.2f}</td>
                        <td>${error:,.2f} ({pct_error:.1f}%)</td>
                    </tr>
                    '''
                
                results_html = f'''
                <div class="status">Showing {len(predictions)} predictions for {selected_year}-{selected_month:02d} (init: {init_time}ms, filter: {filter_time}ms, predict: {predict_time}ms)</div>
                
                <div class="metrics">
                    <div class="metric">
                        <div class="metric-value">{len(predictions)}</div>
                        <div class="metric-label">Records</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${avg_prediction:,.0f}</div>
                        <div class="metric-label">Avg Prediction</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${avg_actual:,.0f}</div>
                        <div class="metric-label">Avg Actual</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{avg_pct_error:.1f}%</div>
                        <div class="metric-label">Avg Error %</div>
                    </div>
                </div>
                
                <h3>Actual vs Predicted Prices</h3>
                <div style="max-width: 800px; margin: 20px 0;">
                    <canvas id="priceChart"></canvas>
                </div>
                <script>
                    new Chart(document.getElementById('priceChart'), {{
                        type: 'bar',
                        data: {{
                            labels: {list(range(1, len(predictions)+1))},
                            datasets: [
                                {{
                                    label: 'Actual Price',
                                    data: {actuals},
                                    backgroundColor: '#000000',
                                    borderColor: '#000000',
                                    borderWidth: 1
                                }},
                                {{
                                    label: 'Predicted Price',
                                    data: {predictions},
                                    backgroundColor: '#e74c3c',
                                    borderColor: '#e74c3c',
                                    borderWidth: 1
                                }}
                            ]
                        }},
                        options: {{
                            responsive: true,
                            plugins: {{
                                title: {{
                                    display: true,
                                    text: 'Actual vs Predicted Housing Prices',
                                    font: {{ size: 16, weight: 'bold' }}
                                }},
                                legend: {{
                                    position: 'top'
                                }}
                            }},
                            scales: {{
                                y: {{
                                    beginAtZero: false,
                                    ticks: {{
                                        callback: function(value) {{
                                            return '$' + value.toLocaleString();
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }});
                </script>
                
                <h3>Prediction Results</h3>
                <table>
                    <tr>
                        <th>#</th>
                        <th>Date</th>
                        <th>Region</th>
                        <th>Actual Price</th>
                        <th>Predicted</th>
                        <th>Error</th>
                    </tr>
                    {table_rows}
                </table>
                '''
        
        total_time = int((time.time() - start_time) * 1000)
        
        html = HTML_TEMPLATE.format(
            year_options=year_options,
            month_options=month_options,
            region_options=region_options,
            results_html=results_html,
            processing_time=total_time
        )
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "text/html",
                "Access-Control-Allow-Origin": "*"
            },
            "body": html
        }
        
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/html"},
            "body": f"<html><body><h1>Error</h1><pre>{str(e)}</pre></body></html>"
        }
