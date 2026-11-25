from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.db.session import engine
from app.services.source_queries import execute_source_query

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@router.get("/ready")
def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT online_revision FROM feature_store.feature_definition LIMIT 1"))
            connection.execute(text("SELECT id FROM core.users LIMIT 1"))
        execute_source_query("SELECT 1 AS ready", 1)
        settings.artifact_storage_dir.mkdir(parents=True, exist_ok=True)
        return {"status": "ready", "cache": settings.online_store_backend}
    except Exception as exc:
        raise HTTPException(503, "Database, migrations, or source reader are not ready") from exc
