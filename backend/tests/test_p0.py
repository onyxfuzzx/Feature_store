import io
import json
import os
import time
from uuid import uuid4

import pytest
from app.core.config import Settings, settings
from app.db.models.core import AuditLog
from app.db.models.feature_store import (
    FeatureDefinition,
    FeatureGroup,
    FeatureValueOffline,
    FeatureValueOnline,
)
from app.db.models.model_registry import Model, ModelVersion
from app.services.artifacts import artifact_path
from app.services.materialization import materialize_feature
from app.services.source_queries import execute_source_query
from app.services.validation import parse_rules, validate_value
from pydantic import ValidationError
from sqlalchemy import text


def create_feature(db, sql="SELECT 'p0_entity' AS entity_key, 7.0 AS value", rules=None):
    group = db.query(FeatureGroup).first()
    feature = FeatureDefinition(
        group_id=group.id,
        name=f"p0_{uuid4().hex}",
        dtype="float",
        source_sql=sql,
        refresh_interval="hourly",
        status="active",
        validation_rules_json=json.dumps(rules) if rules else None,
    )
    db.add(feature)
    db.commit()
    return feature


def upload(client, headers, model_id, version_id, data, filename="model.json"):
    return client.post(
        f"/models/{model_id}/versions/{version_id}/artifact",
        headers=headers,
        files={"file": (filename, data, "application/octet-stream")},
    )


@pytest.mark.parametrize(
    "value,rules",
    [
        ("abc", {"required_type": "int"}),
        ("abc", {"min_value": 0}),
        ("1.5", {"required_type": "int"}),
        ("nan", {"required_type": "float"}),
        ("inf", {"max_value": 10}),
        (None, {"allow_null": False}),
        ("-1", {"min_value": 0}),
    ],
)
def test_validation_rejects_invalid_values(value, rules):
    assert validate_value(value, parse_rules(json.dumps(rules)))


@pytest.mark.parametrize(
    "rules",
    [
        "{bad",
        "[]",
        "null",
        '{"required_type":"code"}',
        '{"min_value":5,"max_value":1}',
        '{"ignore_errors":true}',
    ],
)
def test_invalid_rules_are_rejected(rules):
    with pytest.raises(ValueError):
        parse_rules(rules)


def test_definition_rejects_invalid_rules(client, auth_headers, db):
    group = db.query(FeatureGroup).first()
    response = client.post(
        "/features",
        headers=auth_headers,
        json={
            "group_id": str(group.id),
            "name": "bad",
            "dtype": "float",
            "source_sql": "SELECT 1",
            "refresh_interval": "hourly",
            "validation_rules_json": "[]",
        },
    )
    assert response.status_code == 422


def test_stream_validation_is_atomic(client, auth_headers, db):
    feature = create_feature(db, rules={"allow_null": False, "min_value": 0})
    response = client.post(
        "/features/stream-ingest",
        headers=auth_headers,
        json={
            "records": [
                {"entity_key": "valid", "feature_id": str(feature.id), "value": "1"},
                {"entity_key": "invalid", "feature_id": str(feature.id), "value": "-1"},
            ]
        },
    )
    assert response.status_code == 422
    assert db.query(FeatureValueOnline).filter_by(feature_id=feature.id).count() == 0
    assert db.query(FeatureValueOffline).filter_by(feature_id=feature.id).count() == 0


def test_materialization_rollback_preserves_previous_values(db):
    feature = create_feature(db)
    first = materialize_feature(db, feature.id)
    assert first.status == "success"
    feature.source_sql = "SELECT 'p0_entity' AS entity_key, -1 AS value"
    feature.validation_rules_json = '{"min_value":0}'
    db.commit()
    failed = materialize_feature(db, feature.id)
    assert failed.status == "failed" and "Validation rejected" in failed.error_message
    assert db.query(FeatureValueOnline).filter_by(feature_id=feature.id).one().value == "7.0"
    assert db.query(FeatureValueOffline).filter_by(feature_id=feature.id).count() == 1
    feature.validation_rules_json = None
    feature.source_sql = "SELECT 1 / 0 AS value, 'x' AS entity_key"
    db.commit()
    assert materialize_feature(db, feature.id).status == "failed"
    assert db.execute(text("SELECT 1")).scalar_one() == 1


def test_database_write_failure_rolls_back_all_values(db, monkeypatch):
    feature = create_feature(db)
    assert materialize_feature(db, feature.id).status == "success"
    from app.services import materialization

    class BrokenWriter:
        def write_online_features(self, *args, **kwargs):
            db.execute(text("SELECT 1 / 0"))

    monkeypatch.setattr(materialization, "get_online_store", lambda: BrokenWriter())
    assert materialize_feature(db, feature.id).status == "failed"
    assert db.query(FeatureValueOffline).filter_by(feature_id=feature.id).count() == 1
    assert db.query(FeatureValueOnline).filter_by(feature_id=feature.id).one().value == "7.0"


@pytest.mark.parametrize(
    "query",
    [
        "SELECT password_hash FROM core.users",
        "SELECT key_hash FROM core.api_keys",
        "WITH changed AS (DELETE FROM feature_store.sample_events RETURNING *) SELECT * FROM changed",
        "SELECT 1; DELETE FROM feature_store.sample_events",
        "SELECT pg_read_file('/etc/passwd')",
    ],
)
def test_source_reader_cannot_access_or_mutate_forbidden_data(database, query):
    with pytest.raises(Exception):
        execute_source_query(query, 5)
    assert execute_source_query("SELECT 42 AS value", 1)[1] == [{"value": 42}]


def test_source_timeout_and_result_limit(database, monkeypatch):
    monkeypatch.setattr(settings, "source_query_timeout_ms", 100)
    with pytest.raises(Exception, match="statement timeout"):
        execute_source_query("SELECT pg_sleep(1)", 1)
    assert len(execute_source_query("SELECT generate_series(1, 100) AS value", 3)[1]) == 3


def test_source_rejects_writer_login(database, monkeypatch):
    monkeypatch.setattr(settings, "source_database_url", settings.database_url)
    with pytest.raises(ValueError, match="unprivileged"):
        execute_source_query("SELECT 1", 1)


def test_artifact_scoring_uses_trained_coefficients_and_version(client, auth_headers, db):
    from sklearn.linear_model import LogisticRegression

    classifier = LogisticRegression().fit([[0], [1], [2], [3]], [0, 0, 1, 1])
    feature = create_feature(db)
    assert materialize_feature(db, feature.id).status == "success"
    model = client.post(
        "/models", headers=auth_headers, json={"name": f"trained_{uuid4().hex}"}
    ).json()
    model_id = model["id"]
    versions = []
    for number, sign in [("1", 1), ("2", -1)]:
        version = client.post(
            f"/models/{model_id}/versions", headers=auth_headers, json={"version": number}
        ).json()
        manifest = {
            "format": "featureops.linear.v1",
            "task": "binary_classification",
            "inputs": [{"name": "spend", "feature_id": str(feature.id), "dtype": "float"}],
            "coefficients": [sign * float(classifier.coef_[0][0])],
            "intercept": sign * float(classifier.intercept_[0]),
            "classes": [0, 1],
        }
        assert (
            upload(
                client, auth_headers, model_id, version["id"], json.dumps(manifest).encode()
            ).status_code
            == 200
        )
        versions.append(version)
    first = client.post(
        f"/models/{model_id}/predict",
        headers=auth_headers,
        json={"entity_key": "p0_entity", "version": "1"},
    )
    assert first.status_code == 200, first.text
    expected = float(classifier.predict_proba([[7.0]])[0][1])
    assert first.json()["prediction"]["probability"] == pytest.approx(expected)
    assert first.json()["prediction"]["prediction_class"] == int(classifier.predict([[7.0]])[0])
    second = client.post(
        f"/models/{model_id}/predict",
        headers=auth_headers,
        json={"entity_key": "p0_entity", "version": "2"},
    )
    assert second.json()["prediction"]["probability"] == pytest.approx(1 - expected)
    assert (
        client.post(
            f"/models/{model_id}/predict",
            headers=auth_headers,
            json={"entity_key": "missing", "version": "1"},
        ).status_code
        == 422
    )
    response = client.post(
        f"/models/{model_id}/versions/{versions[0]['id']}/stage",
        headers=auth_headers,
        json={"to_stage": "Production"},
    )
    assert response.status_code == 200 and response.json()["stage"] == "Production"
    detail = client.get(f"/models/versions/{versions[0]['id']}/detail", headers=auth_headers).json()
    assert detail["stage_history"][0]["to_stage"] == "Production"
    assert (
        db.query(AuditLog)
        .filter_by(entity_id=versions[0]["id"], action="PROMOTE_MODEL_VERSION")
        .count()
        == 1
    )
    assert client.post(
        f"/models/{model_id}/predict", headers=auth_headers, json={"entity_key": "p0_entity"}
    ).json()["prediction"]["probability"] == pytest.approx(expected)


def test_artifact_boundaries_and_round_trip(client, auth_headers, db, monkeypatch):
    model = Model(name=f"storage_{uuid4().hex}")
    db.add(model)
    db.flush()
    version = ModelVersion(model_id=model.id, version="storage", stage="Staging")
    db.add(version)
    db.commit()
    for name in ("../escape", "..\\escape", "/tmp/escape", "C:\\escape.bin"):
        from app.services.artifacts import store_artifact
        from fastapi import HTTPException, UploadFile

        with pytest.raises(HTTPException) as rejected:
            store_artifact(
                UploadFile(filename=name, file=io.BytesIO(b"test")), model.id, version.id
            )
        assert rejected.value.status_code == 400
        response = upload(client, auth_headers, model.id, version.id, b"test", name)
        # Multipart parsers normalize some Windows absolute names to a safe basename.
        assert response.status_code == 400 or (
            response.status_code == 200 and response.json()["filename"] == "escape.bin"
        )
    monkeypatch.setattr(settings, "artifact_max_bytes", 16)
    assert upload(client, auth_headers, model.id, version.id, b"x" * 17).status_code == 413
    payload = b"round-trip"
    result = upload(client, auth_headers, model.id, version.id, payload)
    assert result.status_code == 200
    url = f"/models/{model.id}/versions/{version.id}/artifact"
    assert client.get(url, headers=auth_headers).content == payload
    with pytest.raises(Exception):
        artifact_path(f"artifact://{model.id}/{version.id}/../../secret", model.id, version.id)
    assert (
        client.post(
            f"/models/{model.id}/versions",
            headers=auth_headers,
            json={"version": "malicious", "artifact_uri": "file:///etc/passwd"},
        ).status_code
        == 422
    )
    version.artifact_uri = "file:///etc/passwd"
    db.commit()
    assert client.get(url, headers=auth_headers).status_code == 404


def test_redis_commit_rollback_missing_and_recovery(client, auth_headers, db, monkeypatch):
    feature = create_feature(db)
    monkeypatch.setattr(settings, "online_store_backend", "redis")
    monkeypatch.setattr(
        settings, "redis_url", os.environ.get("TEST_REDIS_URL", "redis://localhost:56379/0")
    )
    from app.services.online_store import get_online_store

    store = get_online_store()
    assert store._client.ping()

    def read():
        db.expire_all()
        return store.get_online_features(["cache_entity"], {feature.id: feature.name}, db)[
            "cache_entity"
        ][feature.name]

    def ingest(value, use_name=True):
        ref = {"feature_name": feature.name} if use_name else {"feature_id": str(feature.id)}
        response = client.post(
            "/features/stream-ingest",
            headers=auth_headers,
            json={"records": [{"entity_key": "cache_entity", "value": value, **ref}]},
        )
        assert response.status_code == 201, response.text

    ingest("0")
    assert read() == "0"
    ingest(None, False)
    assert read() is None
    ingest("2")
    assert read() == "2"
    revision = db.get(FeatureDefinition, feature.id).online_revision
    store._client.delete(store.key(feature.id, revision, "cache_entity"))
    assert read() == "2"
    ingest("2.5")
    db.expire_all()
    revision = db.get(FeatureDefinition, feature.id).online_revision
    store._client.pexpire(store.key(feature.id, revision, "cache_entity"), 50)
    time.sleep(0.1)
    assert read() == "2.5"
    store.write_online_features(
        [{"entity_key": "cache_entity", "feature_id": feature.id, "value": "999"}], db
    )
    db.rollback()
    assert read() == "2.5"
    with monkeypatch.context() as outage:
        outage.setattr(
            store._client,
            "pipeline",
            lambda *a, **k: (_ for _ in ()).throw(ConnectionError("offline")),
        )
        outage.setattr(
            store._client, "mget", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("offline"))
        )
        ingest("3")
        assert read() == "3"
    assert read() == "3"  # older Redis key exists but is unreachable after committed revision
    feature = db.get(FeatureDefinition, feature.id)
    feature.source_sql = "SELECT 'cache_entity' AS entity_key, 4 AS value"
    db.commit()
    assert materialize_feature(db, feature.id).status == "success"
    assert read() == "4"
    feature.source_sql = "SELECT 'other_entity' AS entity_key, 5 AS value"
    db.commit()
    assert materialize_feature(db, feature.id).status == "success"
    assert read() is None  # removed entities cannot leak from previous cache generation


@pytest.mark.parametrize(
    "overrides",
    [
        {"jwt_secret": "change-me"},
        {"admin_password": "ChangeMe123!"},
        {"cors_origins": "*"},
        {"source_database_url": None},
    ],
)
def test_production_rejects_placeholder_configuration(overrides):
    config = dict(
        app_env="production",
        jwt_secret="a7" * 24,
        admin_password="b8" * 12,
        cors_origins="https://features.acme.test",
        source_database_url="postgresql://reader:random@db/fs",
    )
    config.update(overrides)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **config)


def test_materialization_size_limit_preserves_previous_refresh(db, monkeypatch):
    feature = create_feature(db)
    assert materialize_feature(db, feature.id).status == "success"
    feature.source_sql = "SELECT n::text AS entity_key, n AS value FROM generate_series(1, 4) n"
    db.commit()
    monkeypatch.setattr(settings, "source_max_rows", 3)
    run = materialize_feature(db, feature.id)
    assert run.status == "failed" and "SOURCE_MAX_ROWS" in run.error_message
    assert db.query(FeatureValueOnline).filter_by(feature_id=feature.id).one().value == "7.0"


def test_runtime_only_inputs_and_regression():
    from app.services.model_runtime import LinearArtifact, score
    from fastapi import HTTPException

    artifact = LinearArtifact.model_validate(
        {
            "format": "featureops.linear.v1",
            "task": "regression",
            "inputs": [{"name": "cart_size", "dtype": "int"}],
            "coefficients": [2],
            "intercept": 1,
        }
    )
    used, prediction = score(artifact, {}, {"cart_size": 3})
    assert prediction == {"value": 7.0}
    for runtime in ({}, {"cart_size": 1.5}, {"cart_size": "nan"}, {"cart_size": 1, "unknown": 2}):
        with pytest.raises(HTTPException) as invalid:
            score(artifact, {}, runtime)
        assert invalid.value.status_code == 422
    classifier = artifact.model_copy(
        update={"task": "binary_classification", "coefficients": [0.0], "intercept": 0.0}
    )
    assert score(classifier, {}, {"cart_size": 0})[1]["prediction_class"] == 0


@pytest.mark.parametrize(
    "change", [{"coefficients": []}, {"coefficients": [float("nan")]}, {"classes": [0, 0]}]
)
def test_invalid_model_contract_is_rejected(change):
    from app.services.model_runtime import LinearArtifact

    artifact = {
        "format": "featureops.linear.v1",
        "task": "binary_classification",
        "inputs": [{"name": "value", "dtype": "float"}],
        "coefficients": [1],
        "intercept": 0,
    }
    artifact.update(change)
    with pytest.raises(ValidationError):
        LinearArtifact.model_validate(artifact)


def test_missing_and_unsupported_models_fail_explicitly(client, auth_headers, db):
    model = Model(name=f"unsupported_{uuid4().hex}")
    db.add(model)
    db.flush()
    version = ModelVersion(model_id=model.id, version="1", stage="Production")
    db.add(version)
    db.commit()
    endpoint = f"/models/{model.id}/predict"
    assert client.post(endpoint, headers=auth_headers, json={"entity_key": "x"}).status_code == 404
    assert (
        upload(client, auth_headers, model.id, version.id, b"opaque binary weights").status_code
        == 200
    )
    assert client.post(endpoint, headers=auth_headers, json={"entity_key": "x"}).status_code == 422
    assert (
        client.post(
            endpoint, headers=auth_headers, json={"entity_key": "x", "version": "absent"}
        ).status_code
        == 404
    )


def test_source_cannot_escalate_role(database):
    with pytest.raises(Exception):
        execute_source_query("SELECT set_config('role', 'postgres', true)", 1)
