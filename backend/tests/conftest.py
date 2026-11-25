"""Integration tests use a dedicated *_test PostgreSQL database, never backend/.env."""

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sdk"))
database_url = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:isolated-test-password@localhost:55432/featureops_test",
)
from sqlalchemy.engine import make_url

if not make_url(database_url).database.endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL must name a disposable database ending in _test")
os.environ.update(
    DATABASE_URL=database_url,
    APP_ENV="test",
    SCHEDULER_ENABLED="false",
    ADMIN_EMAIL="admin@featureops.local",
    ADMIN_PASSWORD="test-admin-credentials",
    SEED_DEMO_DATA="true",
    ONLINE_STORE_BACKEND="postgres",
    SOURCE_ALLOWED_TABLES="feature_store.sample_events",
    SOURCE_QUERY_TIMEOUT_MS="5000",
    SOURCE_MAX_ROWS="100000",
    ACCESS_TOKEN_EXPIRE_MINUTES="30",
    JWT_ALGORITHM="HS256",
    JWT_SECRET="isolated-test-signing-key-for-featureops-64characters-development-only",
)
reader = make_url(database_url).set(
    username="featureops_test_reader", password="isolated-reader-password"
)
os.environ["SOURCE_DATABASE_URL"] = reader.render_as_string(hide_password=False)

import pytest
from app.core.config import settings
from app.db.bootstrap import bootstrap, provision_source_reader
from app.db.models.feature_store import FeatureDefinition
from app.db.seed import seed
from app.db.session import SessionLocal, engine
from app.main import app
from app.services.materialization import materialize_feature
from fastapi.testclient import TestClient
from sqlalchemy import text


@pytest.fixture(scope="session")
def database():
    with TemporaryDirectory(prefix="featureops-test-artifacts-") as directory:
        previous = settings.artifact_storage_dir
        settings.artifact_storage_dir = Path(directory)
        bootstrap()
        # Explicitly guarded disposable DB; repeatable even after interrupted runs.
        with engine.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE core.users, core.roles, feature_store.feature_group, "
                    "model_registry.model, jobs.job_definition CASCADE"
                )
            )
        seed()
        provision_source_reader()
        with SessionLocal() as db:
            feature = db.query(FeatureDefinition).one()
            run = materialize_feature(db, feature.id)
            assert run.status == "success", run.error_message
        yield
        settings.artifact_storage_dir = previous


@pytest.fixture(scope="session")
def client(database):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def admin_token(client):
    response = client.post(
        "/auth/login", json={"email": settings.admin_email, "password": settings.admin_password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def db(database):
    with SessionLocal() as session:
        yield session
        session.rollback()
