from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.ingest.storage import ensure_bucket, get_minio_client
from app.ingest.url_safety import assert_safe_fetch_url


@dataclass
class DownloadResult:
    storage_key: str
    sha256: str
    mime_type: str | None
    size_bytes: int


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=30))
def download_to_minio(url: str, storage_key: str) -> DownloadResult:
    assert_safe_fetch_url(url)

    h = hashlib.sha256()
    mime_type: str | None = None
    size = 0

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with httpx.stream("GET", url, timeout=settings.http_timeout_seconds, follow_redirects=True) as r:
            r.raise_for_status()
            mime_type = r.headers.get("content-type")

            with open(tmp_path, "wb") as f:
                for chunk in r.iter_bytes():
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > settings.max_download_bytes:
                        raise ValueError(f"File too large (> {settings.max_download_bytes} bytes)")
                    h.update(chunk)
                    f.write(chunk)

        client = get_minio_client()
        ensure_bucket(client)

        # Upload
        client.fput_object(
            bucket_name=settings.s3_bucket,
            object_name=storage_key,
            file_path=tmp_path,
            content_type=mime_type,
        )

        return DownloadResult(storage_key=storage_key, sha256=h.hexdigest(), mime_type=mime_type, size_bytes=size)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
