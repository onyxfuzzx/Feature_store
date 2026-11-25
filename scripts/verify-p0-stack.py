"""Verify a disposable stack before/after replacing its backend container."""

import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["before", "after"])
    parser.add_argument("--env-file", default=".cache/p0-stack.env")
    parser.add_argument("--url", default="http://localhost:5188/api")
    parser.add_argument("--state", default=".cache/p0-artifact-state.json")
    args = parser.parse_args()
    if httpx.URL(args.url).host not in {"localhost", "127.0.0.1"}:
        raise ValueError("Verification writes fixtures; target a disposable local stack")
    values = dict(
        line.split("=", 1) for line in Path(args.env_file).read_text().splitlines() if "=" in line
    )
    with httpx.Client(base_url=args.url.rstrip("/") + "/", timeout=30) as client:

        def post(path, data):
            response = client.post(path, json=data)
            response.raise_for_status()
            return response.json()

        response = client.get("ready")
        response.raise_for_status()
        token = post(
            "auth/login", {"email": values["ADMIN_EMAIL"], "password": values["ADMIN_PASSWORD"]}
        )
        client.headers["Authorization"] = f"Bearer {token['access_token']}"
        state_file = Path(args.state)
        if args.phase == "before":
            group = post("features/groups", {"name": f"persistence_{uuid4().hex}"})
            feature = post(
                "features",
                {
                    "group_id": group["id"],
                    "name": f"value_{uuid4().hex}",
                    "dtype": "float",
                    "source_sql": "SELECT 'persistent_entity' AS entity_key, 2 AS value",
                    "refresh_interval": "hourly",
                },
            )
            run = post(f"features/{feature['id']}/materialize", {})
            assert run["status"] == "success", run
            model = post("models", {"name": f"persistent_{uuid4().hex}"})
            version = post(f"models/{model['id']}/versions", {"version": "1"})
            artifact = json.dumps(
                {
                    "format": "featureops.linear.v1",
                    "task": "binary_classification",
                    "inputs": [{"name": "value", "feature_id": feature["id"], "dtype": "float"}],
                    "coefficients": [0.25],
                    "intercept": -1,
                    "classes": [0, 1],
                }
            ).encode()
            response = client.post(
                f"models/{model['id']}/versions/{version['id']}/artifact",
                files={"file": ("persist.json", artifact, "application/json")},
            )
            response.raise_for_status()
            post(f"models/{model['id']}/versions/{version['id']}/stage", {"to_stage": "Production"})
            prediction = post(f"models/{model['id']}/predict", {"entity_key": "persistent_entity"})
            state = {
                "model_id": model["id"],
                "version_id": version["id"],
                "sha256": hashlib.sha256(artifact).hexdigest(),
                "prediction": prediction["prediction"],
            }
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(json.dumps(state))
        state = json.loads(state_file.read_text())
        response = client.get(f"models/{state['model_id']}/versions/{state['version_id']}/artifact")
        response.raise_for_status()
        assert hashlib.sha256(response.content).hexdigest() == state["sha256"]
        prediction = post(
            f"models/{state['model_id']}/predict", {"entity_key": "persistent_entity"}
        )
        assert prediction["prediction"] == state["prediction"]
        print(
            f"P0 stack {args.phase}: readiness, login, artifact bytes and registered prediction verified"
        )


if __name__ == "__main__":
    main()
