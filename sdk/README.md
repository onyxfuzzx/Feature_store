# Feature Store Python SDK & CLI

Official Python SDK and command-line utility for connecting to the Feature Store & Model Registry platform.

## Installation

```bash
pip install -e sdk/
```

## Quickstart

```python
from featurestore import FeatureStoreClient

# Initialize client
client = FeatureStoreClient(
    api_url="http://localhost:8000",
    api_key="fo_your_hashed_or_plain_key"
)

# 1. Fetch online features for low-latency inference
features = client.get_online_features(
    entity_keys=["cust_001", "cust_002"],
    features=["customer_30d_spend"]
)
print("Serving values:", features["values"])
print(f"Lookup latency: {features['read_latency_ms']}ms")

# 2. Build point-in-time correct training set (As-Of Join)
training_data = client.get_historical_features(
    observations=[
        {"entity_key": "cust_001", "event_time": "2026-11-20T12:00:00Z"},
    ],
    features=["customer_30d_spend"]
)
print("Joined rows:", training_data["joined_rows"])

# 3. Stream real-time events directly into online store
client.stream_ingest(
    records=[
        {"entity_key": "cust_001", "feature_name": "customer_30d_spend", "value": "150.25"}
    ]
)
```

## CLI Usage

```bash
# List features
featurestore --url http://localhost:8000 --api-key YOUR_KEY features

# Query real-time online features
featurestore --url http://localhost:8000 --api-key YOUR_KEY get-online --keys cust_001 --features customer_30d_spend
```
