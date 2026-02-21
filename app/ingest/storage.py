from __future__ import annotations

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


def get_minio_client() -> Minio:
    return Minio(
        settings.s3_endpoint,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        secure=settings.s3_secure,
    )


def ensure_bucket(client: Minio) -> None:
    bucket = settings.s3_bucket
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
    except S3Error:
        # In a race (api + worker) bucket may be created simultaneously.
        pass
