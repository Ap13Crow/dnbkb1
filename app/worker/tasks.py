from __future__ import annotations

import traceback

from celery import shared_task

from app.db.session import SessionLocal
from app.db.models import Asset, Job
from app.ingest.downloader import download_to_minio


@shared_task(name="ingest_asset")
def ingest_asset(asset_id: str) -> dict:
    db = SessionLocal()
    try:
        asset = db.get(Asset, asset_id)
        if asset is None:
            return {"status": "missing", "asset_id": asset_id}

        # Idempotency: if already done, skip
        if asset.status == "done":
            return {"status": "done", "asset_id": asset_id, "storage_key": asset.storage_key}

        asset.status = "downloading"
        asset.error = None
        db.commit()

        url = asset.link.url  # relationship
        record_idn = asset.link.record_idn
        storage_key = f"{record_idn}/{asset.id}"

        res = download_to_minio(url, storage_key)

        asset.status = "done"
        asset.storage_key = res.storage_key
        asset.sha256 = res.sha256
        asset.mime_type = res.mime_type
        asset.size_bytes = res.size_bytes
        db.commit()

        return {"status": "done", "asset_id": asset_id, "storage_key": res.storage_key}

    except Exception as e:
        asset = db.get(Asset, asset_id)
        if asset is not None:
            asset.status = "failed"
            asset.error = f"{e}\n{traceback.format_exc()}"
            db.commit()
        return {"status": "failed", "asset_id": asset_id, "error": str(e)}
    finally:
        db.close()


@shared_task(name="finalize_job")
def finalize_job(job_id: str) -> dict:
    """Mark job completed if all assets are terminal (done/failed)."""
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return {"status": "missing", "job_id": job_id}

        assets = [item.asset_id for item in job.items]
        if not assets:
            job.status = "completed"
            db.commit()
            return {"status": "completed", "job_id": job_id}

        # Fetch statuses
        rows = db.query(Asset.status).filter(Asset.id.in_(assets)).all()
        statuses = [s for (s,) in rows]
        if all(s in {"done", "failed"} for s in statuses):
            job.status = "completed"
            db.commit()
            return {"status": "completed", "job_id": job_id}

        return {"status": "running", "job_id": job_id}
    finally:
        db.close()
