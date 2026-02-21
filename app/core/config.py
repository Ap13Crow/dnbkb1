from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- DNB SRU ---
    sru_base_url: str = "https://services.dnb.de/sru/dnb"

    # --- Database ---
    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/dnbkb"

    # --- Queue ---
    celery_broker_url: str = "amqp://guest:guest@rabbitmq:5672//"
    celery_result_backend: str = "db+postgresql://postgres:postgres@db:5432/dnbkb"

    # --- Object storage (MinIO, S3 compatible) ---
    s3_endpoint: str = "minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "dnbkb"
    s3_secure: bool = False

    # --- Ingestion safety ---
    max_download_bytes: int = 50 * 1024 * 1024  # 50MB default
    http_timeout_seconds: float = 30.0


settings = Settings()
