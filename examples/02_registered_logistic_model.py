"""Train, upload, promote, and verify a model served from its registered artifact.

Requires scikit-learn and httpx. Set FEATURE_STORE_URL (e.g. http://localhost:5173/api),
ADMIN_EMAIL, and ADMIN_PASSWORD. Creates its own fixtures and can be rerun.
"""

import json
import os
from uuid import uuid4

import httpx
from sklearn.linear_model import LogisticRegression


def main():
    base_url = os.environ.get("FEATURE_STORE_URL", "http://localhost:5173/api")
    with httpx.Client(base_url=base_url.rstrip("/") + "/", timeout=30) as client:

        def post(path, data):
            response = client.post(path.lstrip("/"), json=data)
            response.raise_for_status()
            return response.json()

        login = post(
            "auth/login",
            {
                "email": os.environ.get("ADMIN_EMAIL", "admin@featureops.local"),
                "password": os.environ["ADMIN_PASSWORD"],
            },
        )
        client.headers["Authorization"] = f"Bearer {login['access_token']}"
        suffix = uuid4().hex[:8]
        group = post("features/groups", {"name": f"Trained example {suffix}"})
        feature = post(
            "features",
            {
                "group_id": group["id"],
                "name": f"spend_{suffix}",
                "dtype": "float",
                "source_sql": "SELECT 'example_customer' AS entity_key, 2.5 AS value",
                "refresh_interval": "hourly",
                "validation_rules_json": '{"allow_null":false,"min_value":0}',
            },
        )
        run = post(f"features/{feature['id']}/materialize", {})
        if run["status"] != "success":
            raise RuntimeError(run["error_message"])
        trained = LogisticRegression().fit([[0], [1], [2], [3]], [0, 0, 1, 1])
        model = post("models", {"name": f"Registered logistic {suffix}"})
        version = post(f"models/{model['id']}/versions", {"version": "1"})
        artifact = {
            "format": "featureops.linear.v1",
            "task": "binary_classification",
            "inputs": [{"name": "spend", "feature_id": feature["id"], "dtype": "float"}],
            "coefficients": trained.coef_[0].tolist(),
            "intercept": float(trained.intercept_[0]),
            "classes": trained.classes_.tolist(),
        }
        response = client.post(
            f"models/{model['id']}/versions/{version['id']}/artifact",
            files={"file": ("trained.json", json.dumps(artifact).encode(), "application/json")},
        )
        response.raise_for_status()
        post(f"models/{model['id']}/versions/{version['id']}/stage", {"to_stage": "Production"})
        prediction = post(f"models/{model['id']}/predict", {"entity_key": "example_customer"})
        expected = float(trained.predict_proba([[2.5]])[0][1])
        actual = prediction["prediction"]["probability"]
        if abs(expected - actual) > 1e-10:
            raise AssertionError(
                f"Registered model score {actual} differs from training runtime {expected}"
            )
        print(f"Verified registered model {model['id']} version 1; probability={actual:.10f}")


if __name__ == "__main__":
    main()
