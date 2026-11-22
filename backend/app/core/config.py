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

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
