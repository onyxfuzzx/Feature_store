"""Scale changes must preserve transaction, ordering, and client contracts."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import jwt
import pytest
from app.api.routes.jobs import get_jobs_overview
from app.core.config import settings
from app.db.models.feature_store import FeatureDefinition, FeatureGroup, FeatureValueOffline
from app.db.models.jobs import JobDefinition, JobRun
from app.db.session import engine
from app.schemas.feature_store import AsOfJoinObservation
from app.services.historical import historical_rows
from app.services.materialization import materialize_feature
from fastapi import Response
from featurestore import FeatureStoreClient, FeatureStoreError
from sqlalchemy import event


def test_historical_one_statement_preserves_duplicates_and_missing(db):
    feature = db.query(FeatureDefinition).first()
    now = datetime.now(UTC)
    key = f"p2-{uuid4()}"
    db.add_all(
        [
            FeatureValueOffline(entity_key=key, feature_id=feature.id, event_time=now, value="1"),
            FeatureValueOffline(
                entity_key=key,
                feature_id=feature.id,
                event_time=now + timedelta(seconds=1),
                value="2",
            ),
        ]
    )
    db.flush()
    observations = [AsOfJoinObservation(entity_key=key, event_time=now)] * 100
    observations.append(AsOfJoinObservation(entity_key="missing", event_time=now))
    queries = []

    def record(*args):
        queries.append(args[2])

    event.listen(engine, "before_cursor_execute", record)
    try:
        rows = historical_rows(db, observations, {feature.id: "value"})
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert len(queries) == 1
    assert len(rows) == 101
    assert all(row["value"] == "1" for row in rows[:100])
    assert rows[-1]["value"] is None


def test_job_overview_two_queries_and_latest_five(db):
    jobs = [
        JobDefinition(
            name=f"p2-{uuid4()}", type="materialization", cron="0 * * * *", is_active=False
        )
        for _ in range(12)
    ]
    db.add_all(jobs)
    db.flush()
    now = datetime.now(UTC)
    for job in jobs:
        db.add_all(
            [
                JobRun(
                    job_definition_id=job.id,
                    status="success",
                    started_at=now + timedelta(seconds=i),
                )
                for i in range(9)
            ]
        )
    db.flush()
    queries = []

    def record(*args):
        queries.append(args[2])

    event.listen(engine, "before_cursor_execute", record)
    try:
        result = get_jobs_overview(Response(), limit=500, offset=0, db=db)
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert len(queries) == 2
    found = [row for row in result if row.id in {job.id for job in jobs}]
    assert len(found) == 12
    assert all(len(row.recent_runs) == 5 for row in found)
    assert all(row.recent_runs[0].started_at > row.recent_runs[-1].started_at for row in found)


def test_pagination_continuation_and_bounds(client, auth_headers):
    first = client.get("/features?limit=1", headers=auth_headers)
    assert first.status_code == 200
    assert len(first.json()) == 1
    assert first.headers["X-Page-Limit"] == "1"
    if "X-Next-Offset" in first.headers:
        second = client.get(
            f"/features?limit=1&offset={first.headers['X-Next-Offset']}", headers=auth_headers
        )
        assert second.json()[0]["id"] != first.json()[0]["id"]
    for query in ("limit=501", "limit=0", "offset=-1", "offset=1000001"):
        assert client.get(f"/features?{query}", headers=auth_headers).status_code == 422


@pytest.mark.parametrize("reverse", [False, True])
def test_online_only_batch_cannot_hide_conflicting_replay(client, auth_headers, db, reverse):
    feature = db.query(FeatureDefinition).first()
    key = f"p2-online-{uuid4()}"
    record = {
        "entity_key": key,
        "feature_id": str(feature.id),
        "value": "10",
        "event_time": "2026-01-01T00:00:00Z",
    }
    assert (
        client.post(
            "/features/stream-ingest",
            headers=auth_headers,
            json={"records": [record], "persist_offline": False},
        ).status_code
        == 201
    )
    records = [
        {**record, "value": "11"},
        {**record, "value": "12", "event_time": "2026-01-02T00:00:00Z"},
    ]
    if reverse:
        records.reverse()
    assert (
        client.post(
            "/features/stream-ingest",
            headers=auth_headers,
            json={"records": records, "persist_offline": False},
        ).status_code
        == 409
    )
    response = client.post(
        "/features/online/batch",
        headers=auth_headers,
        json={"entity_keys": [key], "features": [str(feature.id)]},
    )
    assert list(response.json()["values"][key].values()) == ["10"]


@pytest.mark.parametrize("conflict", [False, True])
def test_materialization_chunk_boundary_atomicity(db, monkeypatch, conflict):
    monkeypatch.setattr(settings, "materialization_batch_size", 2)
    group = FeatureGroup(name=f"p2-{uuid4()}", environment="dev")
    db.add(group)
    db.flush()
    # Same event at a later chunk boundary: exact replay succeeds, changed value fails.
    sql = (
        "SELECT 'p2_chunk' AS entity_key, CASE WHEN i=3 THEN %s ELSE 1 END AS value, TIMESTAMPTZ '2026-01-01' AS event_time FROM generate_series(1,3) i ORDER BY i"
        % (2 if conflict else 1)
    )
    feature = FeatureDefinition(
        group_id=group.id, name="chunked", dtype="int", source_sql=sql, refresh_interval="hourly"
    )
    db.add(feature)
    db.commit()
    feature_id = feature.id
    run = materialize_feature(db, feature_id)
    assert run.status == ("failed" if conflict else "success"), run.error_message
    count = db.query(FeatureValueOffline).filter_by(feature_id=feature_id).count()
    assert count == (0 if conflict else 1)
    assert len(db.info.get("online_publications", [])) == 0


def test_sdk_pagination_borrowed_lifecycle_and_auth():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200,
            json=[{"id": str(len(seen))}],
            headers={"X-Next-Offset": "500"} if len(seen) == 1 else {},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as session:
        with FeatureStoreClient(session=session, api_key="service-key") as sdk:
            assert sdk.list_features() == [{"id": "1"}, {"id": "2"}]
        assert not session.is_closed
        assert seen[1].url.params["offset"] == "500"
        assert seen[0].headers["X-API-Key"] == "service-key"
    sdk = FeatureStoreClient()
    sdk.close()
    assert sdk._session.is_closed


@pytest.mark.parametrize(
    "status,body",
    [(409, {"detail": "Conflicting replay"}), (401, {"detail": "Unauthorized"}), (503, None)],
)
def test_sdk_structured_errors(status, body):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: (
                httpx.Response(status, json=body)
                if body
                else httpx.Response(status, text="unavailable")
            )
        )
    ) as session:
        with FeatureStoreClient(session=session) as sdk:
            with pytest.raises(FeatureStoreError) as caught:
                sdk.list_models()
            assert caught.value.status_code == status


def test_sdk_transport_error():
    def handler(request):
        raise httpx.ReadTimeout("timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as session:
        with pytest.raises(FeatureStoreError, match="ReadTimeout"):
            FeatureStoreClient(session=session).list_models()


def test_jwt_expiration_signature_and_algorithm(client, admin_token):
    payload = jwt.decode(admin_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    tokens = [
        jwt.encode({**payload, "exp": 1}, settings.jwt_secret, algorithm="HS256"),
        jwt.encode(payload, "wrong-signing-key-that-is-long-enough", algorithm="HS256"),
        jwt.encode(payload, settings.jwt_secret, algorithm="HS384"),
    ]
    for token in tokens:
        assert (
            client.get("/features", headers={"Authorization": f"Bearer {token}"}).status_code == 401
        )


def test_cli_token_opt_in_and_close(monkeypatch, capsys):
    import sys

    from featurestore import cli

    closed = []

    class Stub:
        def __init__(self, **kwargs):
            assert kwargs["token"] == "supplied-token"

        def login(self, email, password):
            assert password == "hidden-password"
            return {"user": {"name": "tester"}, "access_token": "sensitive-token"}

        def close(self):
            closed.append(True)

    monkeypatch.setattr(cli, "FeatureStoreClient", Stub)
    monkeypatch.setenv("FEATURE_STORE_PASSWORD", "hidden-password")
    args = ["featurestore", "--token", "supplied-token", "login", "--email", "user@example.test"]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()
    assert "sensitive-token" not in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", args + ["--show-token"])
    cli.main()
    assert capsys.readouterr().out.strip() == "sensitive-token"
    assert len(closed) == 2
