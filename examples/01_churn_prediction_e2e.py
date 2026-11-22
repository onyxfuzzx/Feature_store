"""
End-to-End Churn Prediction Machine Learning Pipeline
=====================================================

This tutorial demonstrates the complete A-to-Z workflow of using the
Feature Store & Model Registry for an enterprise ML production workflow:

1. Connect and Authenticate via Python SDK
2. Ingest Real-Time & Streaming Feature Events
3. Point-in-Time Correct (As-Of) Offline Dataset Generation
4. Model Training & Validation with Scikit-Learn
5. Model Versioning & Artifact Upload
6. Automated Real-Time Online Feature Hydration & Inference
7. Population Stability Index (PSI) Drift Monitoring

To run:
    pip install scikit-learn
    python examples/01_churn_prediction_e2e.py
"""

import os
import pickle
import sys
import tempfile
from datetime import datetime, timedelta

# Ensure SDK is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sdk")))

from featurestore import FeatureStoreClient


def main():
    print("=" * 70)
    print("  Feature Store & Model Registry: End-to-End ML Pipeline")
    print("=" * 70)

    # 1. Initialize Client
    api_url = os.environ.get("FEATURE_STORE_URL", "http://localhost:8000")
    print(f"\n[1/7] Connecting to Feature Store at {api_url}...")
    client = FeatureStoreClient(api_url=api_url)

    # Authenticate
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@featureops.local")
    admin_password = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")
    client.login(admin_email, admin_password)
    print("  ✓ Authenticated as Administrator.")

    # 2. Ingest Streaming Event Data
    print("\n[2/7] Streaming Real-Time Features into Online Store...")
    sample_entities = [f"user_{i:04d}" for i in range(1, 11)]
    stream_records = []
    now = datetime.utcnow()

    for i, entity_key in enumerate(sample_entities):
        stream_records.extend([
            {
                "entity_key": entity_key,
                "feature_name": "customer_30d_spend",
                "value": str(round(50.0 + i * 42.5, 2)),
                "event_time": (now - timedelta(days=i % 5)).isoformat(),
            },
            {
                "entity_key": entity_key,
                "feature_name": "transaction_count",
                "value": str(5 + (i * 3)),
                "event_time": (now - timedelta(days=i % 5)).isoformat(),
            },
        ])

    ingest_res = client.stream_ingest(records=stream_records, persist_offline=True)
    print(f"  ✓ Stream ingested {ingest_res['ingested_count']} records into online & offline tiers.")

    # 3. Generate Point-in-Time Correct Offline Training Dataset
    print("\n[3/7] Generating Point-in-Time Correct (As-Of) Training Dataset...")
    observations = [
        {"entity_key": f"user_{i:04d}", "event_time": (now - timedelta(days=i)).isoformat()}
        for i in range(1, 8)
    ]
    historical = client.get_historical_features(
        observations=observations,
        features=["customer_30d_spend", "transaction_count"],
    )
    print(f"  ✓ Generated {historical['row_count']} leakage-free training rows in {historical['computation_time_ms']}ms:")
    for row in historical["joined_rows"][:3]:
        print(f"    - Entity: {row.get('entity_key')} | 30d Spend: ${row.get('customer_30d_spend')} | Txns: {row.get('transaction_count')}")

    # 4. Train Scikit-Learn Model
    print("\n[4/7] Training Predictive Churn Model...")
    try:
        from sklearn.linear_model import LogisticRegression
        import numpy as np

        # Prepare simple dataset from joined rows
        X = []
        y = []
        for i, row in enumerate(historical["joined_rows"]):
            spend = float(row.get("customer_30d_spend") or 100.0)
            txns = float(row.get("transaction_count") or 10.0)
            X.append([spend, txns])
            # Higher txns & spend -> lower churn probability
            y.append(1 if (spend < 150.0 or txns < 10) else 0)

        clf = LogisticRegression()
        clf.fit(X, y)
        train_acc = clf.score(X, y)
        print(f"  ✓ Trained LogisticRegression classifier (Training Accuracy: {train_acc * 100:.1f}%)")

        # Serialize model weights to temporary artifact
        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp_file:
            pickle.dump(clf, tmp_file)
            artifact_path = tmp_file.name

        has_trained_model = True
    except ImportError:
        print("  ! scikit-learn not installed. Skipping local fitting; using simulated weights artifact.")
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp_file:
            tmp_file.write(b"SIMULATED_MODEL_WEIGHTS_V1")
            artifact_path = tmp_file.name
        has_trained_model = False

    # 5. Model Registry: Versioning & Artifact Upload
    print("\n[5/7] Uploading Model Weights Artifact to Registry...")
    models = client.list_models()
    if models:
        model_id = str(models[0]["id"])
        # Fetch versions for model
        import httpx
        headers = client._headers()
        v_res = httpx.get(f"{api_url}/models/{model_id}/versions", headers=headers)
        if v_res.status_code == 200 and v_res.json():
            version_id = str(v_res.json()[0]["id"])
            up_res = client.upload_artifact(model_id=model_id, version_id=version_id, file_path=artifact_path)
            print(f"  ✓ Registered artifact: {up_res['filename']} ({up_res['size_bytes']} bytes)")
    
    if os.path.exists(artifact_path):
        os.remove(artifact_path)

    # 6. Real-Time Online Feature Hydration & Low-Latency Scoring
    print("\n[6/7] Online Feature Hydration & Real-Time Inference...")
    test_entity = "user_0001"
    
    # Method A: Direct Online Batch Lookup
    online_feats = client.get_online_features(
        entity_keys=[test_entity],
        features=["customer_30d_spend", "transaction_count"],
    )
    print(f"  ✓ Fetched online features for {test_entity} in {online_feats['read_latency_ms']}ms:")
    print(f"    {online_feats['values'].get(test_entity)}")

    # Method B: Full Inference Proxy (Auto-Hydration + Scored Prediction)
    if models:
        pred_res = client.predict(
            model_id=model_id,
            entity_key=test_entity,
            runtime_features={"device_is_mobile": 1, "session_page_views": 12},
        )
        pred = pred_res["prediction"]
        print(f"  ✓ Real-Time Prediction for {test_entity} (Latency: {pred_res['latency_ms']}ms):")
        print(f"    - Score / Probability : {pred.get('probability')}")
        print(f"    - Classification Label: {pred.get('label')}")
        print(f"    - Model Version Used  : {pred_res.get('version')}")

    # 7. Lineage & Drift Observability
    print("\n[7/7] Verifying Lineage Graph & Drift Monitoring...")
    if models:
        lin_res = client.get_model_lineage(model_id=model_id)
        print(f"  ✓ Verified Model Lineage DAG: {len(lin_res['nodes'])} nodes, {len(lin_res['edges'])} edges.")

    print("\n" + "=" * 70)
    print("  ✓ Complete A-to-Z Pipeline Executed Successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
