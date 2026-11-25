"""Reproducible feature history -> training -> registered inference -> measured drift.

Install backend/requirements-test.txt and sdk/; configure FEATURE_STORE_URL,
ADMIN_EMAIL and ADMIN_PASSWORD. Defaults to the Docker same-origin API.
Creates an independent group/model each run; never overwrites an existing model.
"""
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from sklearn.linear_model import LogisticRegression
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk"))
from featurestore import FeatureStoreClient


def main():
    url = os.environ.get("FEATURE_STORE_URL", "http://localhost:5173/api").rstrip("/")
    now = datetime.now(timezone.utc)
    event_time = now - timedelta(days=2)
    observation_time = now - timedelta(days=1)
    suffix = uuid4().hex[:10]
    with httpx.Client(timeout=30) as session:
        sdk = FeatureStoreClient(api_url=url, session=session)
        sdk.login(os.environ.get("ADMIN_EMAIL", "admin@featureops.local"), os.environ["ADMIN_PASSWORD"])
        def post(path, payload):
            response = session.post(url + path, json=payload, headers=sdk._headers())
            response.raise_for_status()
            return response.json()
        group = post("/features/groups", {"name": f"Churn tutorial {suffix}", "environment": "dev"})
        features = []
        for name in ("spend", "transactions"):
            feature = post("/features", {"group_id": group["id"], "name": f"{name}_{suffix}", "dtype": "float",
                "source_sql": "SELECT 'unused' AS entity_key, 0 AS value WHERE false", "refresh_interval": "streaming",
                "status": "active", "validation_rules_json": '{"allow_null":false,"min_value":0}'})
            post(f"/features/{feature['id']}/lineage", {"source_table": "generated:churn_tutorial_events"})
            features.append(feature)
        entities = [f"churn_{suffix}_{i}" for i in range(40)]
        original = [[50.0 + i * 30, 2.0 + i] for i in range(40)]
        def records(matrix, timestamp):
            return [{"entity_key": entity, "feature_id": feature["id"], "value": str(value), "event_time": timestamp.isoformat()}
                    for entity, vector in zip(entities, matrix) for feature, value in zip(features, vector)]
        sdk.stream_ingest(records(original, event_time))
        observations = [{"entity_key": entity, "event_time": observation_time.isoformat()} for entity in entities]
        historical = sdk.get_historical_features(observations, [feature["id"] for feature in features])
        matrix = [[float(row[feature["name"]]) for feature in features] for row in historical["joined_rows"]]
        if matrix != original:
            raise AssertionError("Point-in-time training data differs from the ingested history")
        targets = [int(vector[0] < 500) for vector in matrix]
        training = [index for index in range(40) if index % 5]
        held_out = [index for index in range(40) if not index % 5]
        clf = LogisticRegression(max_iter=2000).fit([matrix[i] for i in training], [targets[i] for i in training])
        accuracy = clf.score([matrix[i] for i in held_out], [targets[i] for i in held_out])
        model = post("/models", {"name": f"Churn Predictor {suffix}", "environment": "dev"})
        version = post(f"/models/{model['id']}/versions", {"version": "1", "metrics_json": json.dumps({"held_out_accuracy": accuracy})})
        manifest = {"format": "featureops.linear.v1", "task": "binary_classification",
            "inputs": [{"name": name, "feature_id": feature["id"], "dtype": "float"} for name, feature in zip(("spend", "transactions"), features)],
            "coefficients": clf.coef_[0].tolist(), "intercept": float(clf.intercept_[0]), "classes": clf.classes_.tolist()}
        response = session.post(f"{url}/models/{model['id']}/versions/{version['id']}/artifact", headers={"Authorization": f"Bearer {sdk.token}"},
                                files={"file": ("churn.json", json.dumps(manifest).encode(), "application/json")})
        response.raise_for_status()
        post(f"/models/versions/{version['id']}/lineage", {"feature_ids_json": json.dumps([feature["id"] for feature in features]),
                                                        "dataset_uri": f"generated://churn/{suffix}/training"})
        post(f"/models/{model['id']}/versions/{version['id']}/drift-baseline", {
            "window_start": (event_time - timedelta(seconds=1)).isoformat(), "window_end": observation_time.isoformat(),
            "samples": {feature["id"]: [matrix[index][column] for index in training] for column, feature in enumerate(features)}})
        post(f"/models/{model['id']}/versions/{version['id']}/stage", {"to_stage": "Production"})
        current = [[vector[0] * 1.5 + 200, vector[1] + 5] for vector in original]
        sdk.stream_ingest(records(current, now))
        # Later online changes must not leak into the original training observations.
        assert sdk.get_historical_features(observations, [feature["id"] for feature in features])["joined_rows"] == historical["joined_rows"]
        expected = clf.predict_proba(current)[:, 1]
        for entity, probability in zip(entities, expected):
            actual = sdk.predict(model["id"], entity)["prediction"]["probability"]
            if abs(actual - float(probability)) > 1e-9:
                raise AssertionError("Registered prediction differs from trained classifier")
        result = post(f"/models/{model['id']}/drift/runs", {"version": "1", "window_start": (now - timedelta(minutes=1)).isoformat(),
            "window_end": (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat(), "min_samples": 20})
        assert result["status"] == "measured" and len(result["metrics"]) == 2
        assert all(metric["current_sample_count"] == 40 and metric["current_psi"] is not None for metric in result["metrics"])
        lineage = sdk.get_model_lineage(model["id"])
        assert any(edge["label"] == "trained_on" for edge in lineage["edges"])
        print(f"Verified churn model {model['id']}: 40 historical rows, held-out accuracy={accuracy:.3f}, 40 matching predictions.")
        print("Persisted PSI:", {metric["feature"]: metric["current_psi"] for metric in result["metrics"]})


if __name__ == "__main__":
    main()
