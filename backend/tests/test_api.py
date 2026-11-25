def test_root_endpoint(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "running"


def test_auth_login_success(client):
    from app.core.config import settings
    res = client.post(
        "/auth/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
    )
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert body["user"]["email"] == settings.admin_email


def test_auth_login_invalid_password(client):
    res = client.post(
        "/auth/login",
        json={"email": "admin@featureops.local", "password": "WrongPassword!"},
    )
    assert res.status_code == 401


def test_auth_me_protected(client, auth_headers):
    res = client.get("/auth/me", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert "email" in body
    assert "admin" in body["roles"]


def test_dashboard_summary(client, auth_headers):
    res = client.get("/dashboard/summary", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert "stats" in body
    assert len(body["stats"]) >= 4
    assert "recent_materializations" in body


def test_list_features(client, auth_headers):
    res = client.get("/features", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_batch_online_feature_serving(client, auth_headers):
    res = client.post(
        "/features/online/batch",
        headers=auth_headers,
        json={
            "entity_keys": ["cust_001", "cust_002"],
            "features": ["customer_30d_spend"],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "values" in body
    assert "cust_001" in body["values"]
    assert "read_latency_ms" in body


def test_as_of_offline_join(client, auth_headers):
    from datetime import datetime
    res = client.post(
        "/features/offline/as-of-join",
        headers=auth_headers,
        json={
            "observations": [
                {"entity_key": "cust_001", "event_time": datetime.utcnow().isoformat()},
            ],
            "features": ["customer_30d_spend"],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "joined_rows" in body
    assert body["row_count"] == 1


def test_streaming_ingest(client, auth_headers):
    res = client.post(
        "/features/stream-ingest",
        headers=auth_headers,
        json={
            "records": [
                {
                    "entity_key": "cust_stream_test",
                    "feature_name": "customer_30d_spend",
                    "value": "999.50",
                }
            ],
            "persist_offline": True,
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    assert body["ingested_count"] >= 1


def test_model_drift_calculation(client, auth_headers):
    # Fetch existing models
    models_res = client.get("/models", headers=auth_headers)
    assert models_res.status_code == 200
    models = models_res.json()
    assert models, "Required fixture data is missing"
    model_id = models[0]["id"]
    drift_res = client.get(f"/models/{model_id}/drift", headers=auth_headers)
    assert drift_res.status_code == 200
    body = drift_res.json()
    assert "metrics" in body
    assert "thresholds" in body
    assert body["status"] == "baseline_missing"
    for m in body["metrics"]:
        assert m["history"] == []
        assert m["current_psi"] is None


def test_jobs_overview(client, auth_headers):
    res = client.get("/jobs/overview", headers=auth_headers)
    assert res.status_code == 200
    jobs = res.json()
    assert isinstance(jobs, list)
    assert jobs, "Required fixture data is missing"
    assert "recent_runs" in jobs[0]


def test_dry_run_query(client, auth_headers):
    res = client.post(
        "/features/dry-run",
        headers=auth_headers,
        json={"query": "SELECT 1 as entity_key, 42.5 as test_val", "limit": 5},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["is_valid"] is True
    assert "entity_key" in body["columns"]
    assert len(body["rows"]) == 1


def test_dry_run_disallows_dml(client, auth_headers):
    res = client.post(
        "/features/dry-run",
        headers=auth_headers,
        json={"query": "DELETE FROM feature_store.raw_events", "limit": 5},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["is_valid"] is False
    assert "disallowed" in body["error"].lower() or "read-only" in body["error"].lower()


def test_feature_lineage_graph(client, auth_headers):
    features_res = client.get("/features", headers=auth_headers)
    assert features_res.status_code == 200
    features = features_res.json()
    assert features, "Required fixture data is missing"
    feat_id = features[0]["id"]
    res = client.get(f"/features/{feat_id}/lineage-graph", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert "nodes" in body
    assert "edges" in body
    assert any(n["type"] == "feature" for n in body["nodes"])


def test_model_lineage_hydrate_predict(client, auth_headers):
    models_res = client.get("/models", headers=auth_headers)
    assert models_res.status_code == 200
    models = models_res.json()
    assert models, "Required fixture data is missing"
    model_id = models[0]["id"]
    # 1. Lineage
    lin_res = client.get(f"/models/{model_id}/lineage-graph", headers=auth_headers)
    assert lin_res.status_code == 200
    assert "nodes" in lin_res.json()

    # 2. Hydrate
    hyd_res = client.post(
        f"/models/{model_id}/hydrate",
        headers=auth_headers,
        json={"entity_keys": ["cust_001"]},
    )
    assert hyd_res.status_code == 200
    hyd_body = hyd_res.json()
    assert "hydrated_records" in hyd_body
    assert "latency_ms" in hyd_body

    # 3. Predict
    pred_res = client.post(
        f"/models/{model_id}/predict",
        headers=auth_headers,
        json={"entity_key": "cust_001", "runtime_features": {}},
    )
    assert pred_res.status_code == 200
    pred_body = pred_res.json()
    assert "prediction" in pred_body
    assert "probability" in pred_body["prediction"]
