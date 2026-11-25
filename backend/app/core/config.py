from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Feature Store"
    app_env: str = "local"
    database_url: str = (
        "postgresql+psycopg2://postgres.xxxxxxxxxxxxxxxxxxxx:YOUR_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
    )
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    cors_origins: str = "http://localhost:5173"
    admin_name: str = "FeatureOps Admin"
    admin_email: str = "admin@featureops.local"
    admin_password: str = "ChangeMe123!"
    online_store_backend: str = "postgres"  # "postgres" or "redis"
    redis_url: str = "redis://localhost:6379/0"
    redis_ttl_seconds: int = Field(default=3600, ge=1)
    source_database_url: str | None = None
    source_allowed_tables: str = "feature_store.sample_events"
    source_query_timeout_ms: int = Field(default=5000, ge=1, le=60000)
    source_max_rows: int = Field(default=100000, ge=1)
    artifact_storage_dir: Path = Path(__file__).resolve().parents[2] / "storage" / "artifacts"
    artifact_max_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    scheduler_enabled: bool = True
    seed_demo_data: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production(self):
        if self.online_store_backend not in {"postgres", "redis"}:
            raise ValueError("ONLINE_STORE_BACKEND must be postgres or redis")
        if self.app_env.lower() in {"production", "prod"}:
            def placeholder(value):
                return any(word in value.lower() for word in (
                    "change", "replace", "your", "password123", "example", "secret-key"
                ))
            if len(self.jwt_secret) < 32 or placeholder(self.jwt_secret):
                raise ValueError("Production requires a random JWT_SECRET of at least 32 characters")
            if len(self.admin_password) < 12 or placeholder(self.admin_password):
                raise ValueError("Production requires a non-placeholder ADMIN_PASSWORD of at least 12 characters")
            if not self.source_database_url:
                raise ValueError("Production requires SOURCE_DATABASE_URL for a restricted reader")
            origins = self.cors_origin_list()
            if not origins or any(o == "*" or not o.startswith("https://") for o in origins):
                raise ValueError("Production CORS_ORIGINS must list explicit HTTPS origins")
        return self


settings = Settings()
