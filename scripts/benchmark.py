"""Repeatable local benchmark. Clears ONLY the explicitly selected *_bench database.

Run with the locked backend test dependencies; see docs/PERFORMANCE.md.
"""

import argparse
import json
import logging
import os
import platform
import sys
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import event, text
from sqlalchemy.engine import make_url

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--database-url",
    default="postgresql+psycopg2://postgres:disposable-benchmark-password@localhost:55433/featureops_bench",
)
parser.add_argument("--redis-url", default="redis://localhost:56380/0")
parser.add_argument("--samples", type=int, default=100)
parser.add_argument("--output", type=Path, default=Path(".cache/benchmark.json"))
args = parser.parse_args()
if not make_url(args.database_url).database.endswith("_bench") or args.samples < 20:
    parser.error("Use a disposable *_bench database and at least 20 samples")
reader = make_url(args.database_url).set(
    username="featureops_bench_reader", password="disposable-benchmark-reader"
)
os.environ.update(
    DATABASE_URL=args.database_url,
    SOURCE_DATABASE_URL=reader.render_as_string(hide_password=False),
    REDIS_URL=args.redis_url,
    APP_ENV="test",
    SCHEDULER_ENABLED="false",
    SEED_DEMO_DATA="false",
    JWT_SECRET="disposable-benchmark-signing-key-32chars",
    ADMIN_PASSWORD="disposable-benchmark-admin",
    ADMIN_EMAIL="bench@example.test",
    ONLINE_STORE_BACKEND="redis",
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.api.routes.jobs import get_jobs_overview
from app.core.config import settings
from app.db.bootstrap import bootstrap
from app.db.models.feature_store import FeatureDefinition, FeatureGroup, FeatureValueOffline
from app.db.models.jobs import JobDefinition, JobRun
from app.db.session import SessionLocal, engine
from app.main import app
from app.schemas.feature_store import AsOfJoinObservation
from app.services.historical import historical_rows
from app.services.materialization import materialize_feature
from fastapi import Response
from fastapi.testclient import TestClient


def measure(call, samples):
    values = []
    started = time.perf_counter()
    for _ in range(samples):
        before = time.perf_counter()
        call()
        values.append(1000 * (time.perf_counter() - before))
    return summary(values, time.perf_counter() - started)


def summary(values, seconds):
    values = sorted(values)
    return {
        "samples": len(values),
        "p50_ms": round(values[int((len(values) - 1) * 0.5)], 3),
        "p95_ms": round(values[int((len(values) - 1) * 0.95)], 3),
        "p99_ms": round(values[int((len(values) - 1) * 0.99)], 3),
        "requests_per_second": round(len(values) / seconds, 2),
    }


def query_count(call):
    statements = []

    def record(*values):
        statements.append(values[2])

    event.listen(engine, "before_cursor_execute", record)
    try:
        call()
    finally:
        event.remove(engine, "before_cursor_execute", record)
    return len(statements)


with TemporaryDirectory(prefix="featureops-bench-artifacts-") as artifacts:
    settings.artifact_storage_dir = Path(artifacts)
    bootstrap()
    with engine.begin() as connection:
        # No application or *_test database can pass the guard above.
        connection.execute(
            text(
                "TRUNCATE feature_store.feature_group, model_registry.model, jobs.job_definition CASCADE"
            )
        )
    with SessionLocal() as db:
        group = FeatureGroup(name="benchmark", environment="dev")
        db.add(group)
        db.flush()
        features = [
            FeatureDefinition(
                group_id=group.id,
                name=f"bench_{i}",
                dtype="float",
                source_sql="SELECT 'materialized_' || i AS entity_key, i AS value, TIMESTAMPTZ '2026-01-01' AS event_time FROM generate_series(1,10000) i",
                refresh_interval="hourly",
            )
            for i in range(5)
        ]
        db.add_all(features)
        db.flush()
        ids = [f.id for f in features]
        db.execute(
            text(
                "INSERT INTO feature_store.feature_values_offline(entity_key,feature_id,event_time,value) SELECT 'entity_' || e, f, TIMESTAMPTZ '2026-01-01' + t * INTERVAL '1 hour', (e + t)::text FROM generate_series(1,1000) e CROSS JOIN generate_series(0,19) t CROSS JOIN unnest(CAST(:ids AS uuid[])) f"
            ),
            {"ids": [str(i) for i in ids]},
        )
        db.execute(
            text(
                "INSERT INTO feature_store.feature_values_online(entity_key,feature_id,event_time,value) SELECT entity_key,feature_id,event_time,value FROM feature_store.feature_values_offline WHERE event_time=TIMESTAMPTZ '2026-01-01 19:00:00Z'"
            )
        )
        jobs = [
            JobDefinition(
                name=f"benchmark_{i}",
                type="materialization",
                cron="0 * * * *",
                is_active=False,
                payload_json=json.dumps({"feature_id": str(ids[0])}),
            )
            for i in range(100)
        ]
        db.add_all(jobs)
        db.flush()
        db.add_all(
            [
                JobRun(
                    job_definition_id=j.id,
                    status="success",
                    started_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=i),
                )
                for j in jobs
                for i in range(10)
            ]
        )
        db.commit()
        db.execute(text("ANALYZE feature_store.feature_values_offline"))
        db.commit()
    report = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "environment": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "packages": {
                p: version(p) for p in ["fastapi", "sqlalchemy", "psycopg2-binary", "redis"]
            },
        },
        "scope": "TestClient in-process HTTP; real PostgreSQL/Redis over Docker network. No external HTTP/TLS latency or production SLO.",
        "dataset": {
            "offline_rows": 100000,
            "online_rows": 5000,
            "features": 5,
            "entities": 1000,
            "events_per_entity_feature": 20,
            "jobs": 100,
            "job_runs": 1000,
            "materialization_rows": 10000,
            "chunk_size": settings.materialization_batch_size,
        },
    }
    observations = [
        AsOfJoinObservation(
            entity_key=f"entity_{i}", event_time=datetime(2026, 1, 1, 10, 30, tzinfo=UTC)
        )
        for i in range(1, 101)
    ]
    mapping = {fid: f"bench_{i}" for i, fid in enumerate(ids)}
    with SessionLocal() as db:

        def historical():
            rows = historical_rows(db, observations, mapping)
            assert len(rows) == 100 and rows[0]["bench_0"] == "11"

        def reference():
            for obs in observations:
                for fid in ids:
                    value = (
                        db.query(FeatureValueOffline.value)
                        .filter(
                            FeatureValueOffline.entity_key == obs.entity_key,
                            FeatureValueOffline.feature_id == fid,
                            FeatureValueOffline.event_time <= obs.event_time,
                        )
                        .order_by(FeatureValueOffline.event_time.desc())
                        .limit(1)
                        .scalar()
                    )
                    assert value is not None

        historical()
        report["historical_100x5_sql"] = measure(historical, args.samples)
        report["historical_previous_lookup_reference"] = measure(reference, 20)
        report["query_counts"] = {
            "historical_batch": query_count(historical),
            "historical_previous_reference": query_count(reference),
            "jobs_overview_100": query_count(
                lambda: get_jobs_overview(Response(), limit=100, offset=0, db=db)
            ),
        }
    logging.getLogger("httpx").setLevel(logging.WARNING)
    with TestClient(app) as client:
        login = client.post(
            "/auth/login", json={"email": settings.admin_email, "password": settings.admin_password}
        )
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        online = {
            "entity_keys": [f"entity_{i}" for i in range(1, 21)],
            "features": [str(i) for i in ids],
        }
        offline = {
            "observations": [o.model_dump(mode="json") for o in observations],
            "features": [str(i) for i in ids],
        }

        def post(path, payload):
            response = client.post(path, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

        post("/features/online/batch", online)  # Warm the measured revision.
        report["online_20x5_warm_http"] = measure(
            lambda: post("/features/online/batch", online), args.samples
        )
        report["offline_100x5_http"] = measure(
            lambda: post("/features/offline/as-of-join", offline), args.samples
        )

        def concurrent(i):
            started = time.perf_counter()
            if i % 5 == 0:
                post(
                    "/features/stream-ingest",
                    {
                        "records": [
                            {
                                "entity_key": f"concurrent_{i}",
                                "feature_id": str(ids[0]),
                                "value": "12",
                                "event_time": "2026-02-01T00:00:00Z",
                            }
                        ]
                    },
                )
                kind = "write"
            else:
                values = post("/features/online/batch", online)
                assert values["values"]["entity_1"]["bench_0"] == "20"
                kind = "read"
            return kind, 1000 * (time.perf_counter() - started)

        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(concurrent, range(args.samples * 2)))
        elapsed = time.perf_counter() - started
        report["concurrent_8_workers"] = {
            kind: summary([ms for k, ms in results if k == kind], elapsed)
            for kind in ["read", "write"]
        }
        report["concurrent_8_workers"]["errors"] = 0
    with SessionLocal() as db:

        def refresh():
            run = materialize_feature(db, ids[1])
            assert run.status == "success" and run.row_count == 10000, run.error_message

        report["materialization_10000"] = measure(refresh, 5)
        tracemalloc.start()
        refresh()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        report["materialization_10000"]["python_traced_peak_bytes"] = peak
        report["materialization_10000"]["post_commit_queue_entries"] = len(
            db.info.get("online_publications", [])
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
