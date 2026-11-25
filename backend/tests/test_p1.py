import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.db.models.core import User, AuditLog
from app.db.models.feature_store import FeatureDefinition, FeatureGroup, FeatureValueOnline, FeatureValueOffline
from app.db.models.model_registry import ModelVersion, ModelStageHistory, DriftRun, InferenceObservation
from app.db.models.jobs import JobDefinition, JobRun
from app.jobs import scheduler


@pytest.fixture
def api(client, auth_headers):
    def call(path, data):
        response = client.post(path, headers=auth_headers, json=data)
        assert response.status_code in (200, 201), response.text
        return response.json()
    return call


def feature(api, name=None, environment="dev", group=None, sql="SELECT 'entity' AS entity_key, 1 AS value"):
    group = group or api("/features/groups", {"name": f"Group_{uuid4().hex}", "environment": environment})
    return api("/features", {"group_id": group["id"], "name": name or f"value_{uuid4().hex}", "dtype": "float",
                             "source_sql": sql, "refresh_interval": "hourly", "status": "active"})


def serving_model(api, client, headers, source):
    model = api("/models", {"name": f"Model_{uuid4().hex}"})
    version = api(f"/models/{model['id']}/versions", {"version": "1", "stage": "Production"})
    manifest = {"format": "featureops.linear.v1", "task": "binary_classification",
                "inputs": [{"name": "value", "feature_id": source["id"], "dtype": "float"}],
                "coefficients": [0.5], "intercept": -1, "classes": [0, 1]}
    response = client.post(f"/models/{model['id']}/versions/{version['id']}/artifact", headers=headers,
                           files={"file": ("model.json", json.dumps(manifest).encode(), "application/json")})
    assert response.status_code == 200, response.text
    return model, version, manifest


def test_recorded_drift_is_version_scoped_and_preserves_zero(api, client, auth_headers, db):
    source = feature(api)
    model, version, manifest = serving_model(api, client, auth_headers, source)
    now = datetime.now(timezone.utc)
    baseline = api(f"/models/{model['id']}/versions/{version['id']}/drift-baseline", {
        "window_start": (now - timedelta(days=2)).isoformat(), "window_end": (now - timedelta(days=1)).isoformat(),
        "samples": {source["id"]: [0, 1, 2, 3]}})
    for value in range(4):
        api("/features/stream-ingest", {"records": [{"entity_key": str(value), "feature_id": source["id"], "value": str(value)}]})
        api(f"/models/{model['id']}/predict", {"entity_key": str(value)})
    payload = {"window_start": (now - timedelta(minutes=1)).isoformat(), "window_end": (now + timedelta(minutes=1)).isoformat(), "min_samples": 2}
    result = api(f"/models/{model['id']}/drift/runs", payload)
    assert result["status"] == "measured"
    assert result["metrics"][0]["current_psi"] == 0
    assert result["metrics"][0]["current_sample_count"] == 4
    summary = client.get(f"/models/{model['id']}/drift", headers=auth_headers).json()
    assert summary["metrics"][0]["history"] == [{"date": summary["latest_run"]["created_at"], "run_id": result["id"],
        "psi": 0.0, "status": "measured", "window_start": summary["latest_run"]["window_start"], "window_end": summary["latest_run"]["window_end"]}]
    assert db.query(InferenceObservation).filter_by(model_version_id=UUID(version["id"])).count() == 4
    second = api(f"/models/{model['id']}/versions", {"version": "2"})
    other = api(f"/models/{model['id']}/drift/runs", {**payload, "version": "2"})
    assert other["status"] == "insufficient_data" and other["metrics"] == []
    assert client.get(f"/models/{model['id']}/drift?version=2", headers=auth_headers).json()["baseline"] is None
    unknown = feature(api)
    response = client.post(f"/models/{model['id']}/versions/{version['id']}/drift-baseline", headers=auth_headers,
                           json={"window_start": payload["window_start"], "window_end": payload["window_end"], "samples": {unknown["id"]: [1, 2]}})
    assert response.status_code == 422
    insufficient = api(f"/models/{model['id']}/drift/runs", {**payload, "min_samples": 20})
    assert insufficient["metrics"][0]["current_psi"] is None
    assert insufficient["metrics"][0]["drift_detected"] is None
    assert db.query(DriftRun).filter_by(model_version_id=UUID(version["id"])).count() == 2


def test_drift_uses_recorded_window_and_fixed_baseline(api, client, auth_headers):
    source = feature(api)
    model, version, _ = serving_model(api, client, auth_headers, source)
    now = datetime.now(timezone.utc)
    api(f"/models/{model['id']}/versions/{version['id']}/drift-baseline", {
        "window_start": (now - timedelta(days=2)).isoformat(), "window_end": (now - timedelta(days=1)).isoformat(),
        "samples": {source["id"]: [1] * 20}})
    for index in range(4):
        api("/features/stream-ingest", {"records": [{"entity_key": str(index), "feature_id": source["id"], "value": "100"}]})
        api(f"/models/{model['id']}/predict", {"entity_key": str(index)})
    measured = api(f"/models/{model['id']}/drift/runs", {"window_start": (now - timedelta(seconds=1)).isoformat(),
        "window_end": (now + timedelta(minutes=1)).isoformat(), "min_samples": 2})
    assert measured["metrics"][0]["current_psi"] > 0.2
    empty = api(f"/models/{model['id']}/drift/runs", {"window_start": (now - timedelta(hours=2)).isoformat(),
        "window_end": (now - timedelta(hours=1)).isoformat(), "min_samples": 2})
    assert empty["metrics"][0]["current_sample_count"] == 0 and empty["metrics"][0]["current_psi"] is None


def test_feature_identity_collisions_and_scope(api, client, auth_headers):
    name = "shared_" + uuid4().hex
    first = feature(api, name=name)
    second = feature(api, name=name, environment="staging")
    for item, value in ((first, "10"), (second, "20")):
        api("/features/stream-ingest", {"records": [{"entity_key": "scope", "feature_id": item["id"], "value": value}]})
    response = client.post("/features/online/batch", headers=auth_headers, json={"entity_keys": ["scope"], "features": [name]})
    assert response.status_code == 422 and "Ambiguous" in response.text
    scoped = api("/features/online/batch", {"entity_keys": ["scope"], "features": [name], "environment": "staging"})
    assert scoped["values"]["scope"][name] == "20"
    combined = api("/features/online/batch", {"entity_keys": ["scope"], "features": [first["id"], second["id"]]})
    assert set(combined["values"]["scope"].values()) == {"10", "20"}
    assert len(combined["features"]) == 2 and all(":" in key for key in combined["features"])
    references = combined["features"]
    again = api("/features/online/batch", {"entity_keys": ["scope"], "features": references})
    assert again["values"] == combined["values"]
    assert client.post("/features/online/batch", headers=auth_headers,
        json={"entity_keys": ["scope"], "features": ["missing_" + uuid4().hex]}).status_code == 422
    assert client.post("/features/online/batch", headers=auth_headers,
        json={"entity_keys": ["scope"], "features": [first["id"], first["id"]]}).status_code == 422


def test_replays_late_events_and_point_in_time_boundaries(api, client, auth_headers, db):
    source = feature(api)
    now = datetime.now(timezone.utc)
    old = now - timedelta(hours=2)
    def ingest(value, at, persist=True):
        return client.post("/features/stream-ingest", headers=auth_headers, json={"persist_offline": persist,
            "records": [{"entity_key": "temporal", "feature_id": source["id"], "value": value, "event_time": at.isoformat()}]})
    assert ingest("10", old).status_code == 201
    assert ingest("20", now).status_code == 201
    assert ingest("10", old).status_code == 201  # exact replay is a no-op
    assert ingest("99", old).status_code == 409  # conflicting history is not silently rewritten
    assert ingest("99", now, False).status_code == 409  # same protection without offline writes
    assert api("/features/online/batch", {"entity_keys": ["temporal"], "features": [source["id"]]})["values"]["temporal"][source["name"]] == "20"
    assert db.query(FeatureValueOffline).filter_by(feature_id=UUID(source["id"])).count() == 2
    rows = api("/features/offline/as-of-join", {"features": [source["id"]], "observations": [
        {"entity_key": "temporal", "event_time": timestamp.isoformat()} for timestamp in (old - timedelta(microseconds=1), old, now - timedelta(microseconds=1), now)]})["joined_rows"]
    assert [row[source["name"]] for row in rows] == [None, "10", "10", "20"]


@pytest.mark.parametrize("change", [{"cron": "not cron"}, {"type": "arbitrary"}, {"payload_json": "{"},
                                     {"payload_json": "{}"}, {"payload_json": '{"feature_id":123}'}, {"payload_json": None}])
def test_invalid_job_definitions_never_persist(api, client, auth_headers, db, change):
    source = feature(api)
    name = "invalid_" + uuid4().hex
    response = client.post("/jobs", headers=auth_headers, json={"name": name, "cron": "* * * * *", "type": "feature_materialization",
        "payload_json": json.dumps({"feature_id": source["id"]}), **change})
    assert response.status_code == 422, response.text
    assert db.query(JobDefinition).filter_by(name=name).count() == 0


def test_job_pause_edit_and_failed_materialization_status(api, client, auth_headers, db):
    source = feature(api, sql="SELECT 1/0 AS value, 'x' AS entity_key")
    payload = {"name": "job_" + uuid4().hex, "cron": "* * * * *", "type": "feature_materialization", "payload_json": json.dumps({"feature_id": source["id"]}), "is_active": True}
    job = api("/jobs", payload)
    paused = client.put(f"/jobs/{job['id']}", headers=auth_headers, json={**payload, "is_active": False})
    assert paused.status_code == 200 and paused.json()["is_active"] is False
    assert scheduler._run_job(job["id"], scheduled=True) is None
    run = api(f"/jobs/{job['id']}/run", {})
    assert run["status"] == "failed" and "division by zero" in run["log"]
    assert client.put(f"/jobs/{job['id']}", headers=auth_headers, json={**payload, "cron": "invalid"}).status_code == 422
    db.expire_all()
    assert db.get(JobDefinition, UUID(job["id"])).is_active is False


def test_database_lock_and_scheduled_slot_prevent_duplicate_runs(api, db, monkeypatch):
    source = feature(api)
    job = api("/jobs", {"name": "coordinated_" + uuid4().hex, "cron": "* * * * *", "type": "feature_materialization", "payload_json": json.dumps({"feature_id": source["id"]})})
    entered, release = Event(), Event()
    original = scheduler.materialize_feature
    def delayed(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(scheduler, "materialize_feature", delayed)
    slot = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(scheduler._run_job, job["id"], True, slot)
        assert entered.wait(5)
        try:
            assert scheduler._run_job(job["id"], True, slot) is None
        finally:
            release.set()
        assert pending.result(timeout=10) is not None
    assert scheduler._run_job(job["id"], True, slot) is None
    assert db.query(JobRun).filter_by(job_definition_id=UUID(job["id"]), scheduled_for=slot).count() == 1


def test_registry_uniqueness_and_concurrent_promotions(api, client, auth_headers, db):
    model = api("/models", {"name": "concurrent_" + uuid4().hex})
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: client.post(f"/models/{model['id']}/versions", headers=auth_headers, json={"version": "1"}).status_code, range(2)))
    assert sorted(statuses) == [201, 409]
    first = client.get(f"/models/{model['id']}/versions", headers=auth_headers).json()[0]
    second = api(f"/models/{model['id']}/versions", {"version": "2"})
    assert client.post(f"/models/{model['id']}/versions", headers=auth_headers, json={"version": "3", "stage": "Invalid"}).status_code == 422
    def promote(item):
        return client.post(f"/models/{model['id']}/versions/{item['id']}/stage", headers=auth_headers, json={"to_stage": "Production"}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(promote, (first, second))) == [200, 200]
    versions = db.query(ModelVersion).filter_by(model_id=UUID(model["id"])).all()
    assert sorted(item.stage for item in versions) == ["Archived", "Production"]
    assert db.query(ModelStageHistory).filter(ModelStageHistory.model_version_id.in_([item.id for item in versions])).count() == 3


def test_promotion_audit_failure_rolls_back_stage_and_history(api, client, auth_headers, db, monkeypatch):
    model = api("/models", {"name": "atomic_" + uuid4().hex})
    version = api(f"/models/{model['id']}/versions", {"version": "1"})
    from app.services import registry
    monkeypatch.setattr(registry, "log_audit", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("forced audit failure")))
    with pytest.raises(RuntimeError, match="forced audit"):
        client.post(f"/models/{model['id']}/versions/{version['id']}/stage", headers=auth_headers, json={"to_stage": "Production"})
    db.expire_all()
    assert db.get(ModelVersion, UUID(version["id"])).stage == "Staging"
    assert db.query(ModelStageHistory).filter_by(model_version_id=UUID(version["id"])).count() == 0


def test_invalid_user_roles_leave_no_user(client, auth_headers, db):
    email = uuid4().hex + "@example.test"
    response = client.post("/users", headers=auth_headers, json={"name": "Invalid", "email": email, "password": "Valid-Test-Password!", "roles": ["unknown"]})
    assert response.status_code == 400
    assert db.query(User).filter_by(email=email).count() == 0


def test_user_and_roles_rollback_when_auditing_fails(client, auth_headers, db, monkeypatch):
    from app.api.routes import users
    email = uuid4().hex + "@example.test"
    monkeypatch.setattr(users, "log_audit", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("audit unavailable")))
    with pytest.raises(RuntimeError, match="audit unavailable"):
        client.post("/users", headers=auth_headers, json={"name": "Atomic", "email": email,
                    "password": "Valid-Test-Password!", "roles": ["analyst"]})
    assert db.query(User).filter_by(email=email).count() == 0


@pytest.mark.parametrize("role", ["admin", "ml_engineer", "data_scientist", "analyst"])
def test_role_and_api_key_permissions(api, client, auth_headers, db, role):
    email, password = uuid4().hex + "@example.test", "Valid-Test-Password!"
    user = api("/users", {"name": role, "email": email, "password": password, "roles": [role]})
    token = client.post("/auth/login", json={"email": email, "password": password}).json()["access_token"]
    bearer = {"Authorization": "Bearer " + token}
    assert client.get("/features", headers=bearer).status_code == 200
    assert client.get("/users", headers=bearer).status_code == (200 if role == "admin" else 403)
    assert client.get("/jobs", headers=bearer).status_code == (403 if role == "analyst" else 200)
    response = client.post("/features/groups", headers=bearer, json={"name": uuid4().hex})
    assert response.status_code == (403 if role == "analyst" else 201)
    source = feature(api)
    assert client.post(f"/features/{source['id']}/materialize", headers=bearer).status_code == (201 if role in {"admin", "ml_engineer"} else 403)
    model_response = client.post("/models", headers=bearer, json={"name": uuid4().hex})
    assert model_response.status_code == (403 if role == "analyst" else 201)
    assert client.post("/jobs", headers=bearer, json={"name": uuid4().hex, "type": "feature_materialization", "cron": "0 * * * *",
        "payload_json": json.dumps({"feature_id": source["id"]})}).status_code == (201 if role in {"admin", "ml_engineer"} else 403)
    key = client.post("/api-keys", headers=bearer, json={"name": "role test"}).json()
    assert key["plain_key"].startswith("fo_")
    assert "plain_key" not in client.get("/api-keys", headers=bearer).json()[0]
    key_headers = {"X-API-Key": key["plain_key"]}
    assert client.get("/features", headers=key_headers).status_code == 200
    assert client.get("/users", headers=key_headers).status_code == (200 if role == "admin" else 403)
    if role != "admin":
        assert client.delete(f"/api-keys/{key['id']}", headers=auth_headers).status_code == 404
    assert client.delete(f"/api-keys/{key['id']}", headers=bearer).status_code == 204
    assert client.get("/features", headers=key_headers).status_code == 401
    user_row = db.get(User, UUID(user["id"]))
    user_row.is_active = False
    db.commit()
    assert client.get("/features", headers=bearer).status_code == 401


def test_lineage_keeps_shared_feature_edges_and_real_sources(api, client, auth_headers):
    source = feature(api)
    model, first, manifest = serving_model(api, client, auth_headers, source)
    second = api(f"/models/{model['id']}/versions", {"version": "2"})
    api(f"/models/versions/{second['id']}/lineage", {"feature_ids_json": json.dumps([source["id"]])})
    graph = client.get(f"/models/{model['id']}/lineage-graph", headers=auth_headers).json()
    assert len([node for node in graph["nodes"] if node["id"] == "feat:" + source["id"]]) == 1
    assert len([edge for edge in graph["edges"] if edge["source"] == "feat:" + source["id"] and edge["label"] == "trained_on"]) == 2
    assert any(node["type"] == "unknown_source" for node in graph["nodes"])
    assert not any("raw_events" in node["label"] for node in graph["nodes"])
    api(f"/features/{source['id']}/lineage", {"source_table": "sources.registered_payments"})
    graph = client.get(f"/features/{source['id']}/lineage-graph", headers=auth_headers).json()
    assert any(node["label"] == "sources.registered_payments" for node in graph["nodes"])
    assert not any(node["type"] == "unknown_source" for node in graph["nodes"])
    assert client.post(f"/models/versions/{first['id']}/lineage", headers=auth_headers,
                       json={"feature_ids_json": "[]"}).status_code == 422


def test_readiness_failure_and_empty_freshness_are_honest(client, auth_headers, db, monkeypatch):
    from app.api.routes import health
    monkeypatch.setattr(health, "execute_source_query", lambda *a, **k: (_ for _ in ()).throw(ValueError("offline")))
    assert client.get("/ready").status_code == 503
    old = [(item.id, item.status) for item in db.query(FeatureDefinition)]
    try:
        db.query(FeatureDefinition).update({"status": "draft"})
        db.commit()
        summary = client.get("/dashboard/summary", headers=auth_headers).json()
        assert next(stat for stat in summary["stats"] if stat["label"] == "Data Freshness")["value"] == "N/A"
    finally:
        for identity, status in old:
            db.get(FeatureDefinition, identity).status = status
        db.commit()
