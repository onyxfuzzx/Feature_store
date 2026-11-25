from tempfile import TemporaryFile

from app.core.config import settings
from app.db.session import engine
from app.services.online_store import get_online_store
from app.services.source_queries import execute_source_query
from fastapi import APIRouter, HTTPException
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@router.get("/ready")
def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(
                text("SELECT online_revision FROM feature_store.feature_definition LIMIT 1")
            )
            connection.execute(text("SELECT id FROM core.users LIMIT 1"))
        execute_source_query("SELECT 1 AS ready", 1)
        settings.artifact_storage_dir.mkdir(parents=True, exist_ok=True)
        with TemporaryFile(dir=settings.artifact_storage_dir):
            pass
        cache = "postgres"
        if settings.online_store_backend == "redis":
            try:
                get_online_store()._client.ping()
                cache = "redis"
            except Exception:
                cache = "postgres_fallback"
        return {
            "status": "ready",
            "cache": cache,
            "checks": {"database": "ready", "source_reader": "ready", "artifacts": "ready"},
        }
    except Exception as exc:
        raise HTTPException(503, "Database, migrations, or source reader are not ready") from exc
