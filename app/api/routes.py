from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import (
    AssetOut,
    IngestRequest,
    IngestResponse,
    JobResponse,
    RecordResponse,
    SearchRequest,
    SearchResponse,
    SearchHit,
    LinkOut,
)
from app.db.models import Asset, Job, JobItem, Link, Record
from app.db.session import get_db
from app.dnb.marc import parse_marcxml_record
from app.dnb.sru_client import SruClient
from app.ingest.storage import get_minio_client
from app.core.config import settings
from app.worker.celery_app import celery_app

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    # Run SRU query (async client) from sync endpoint: use anyio via httpx? We'll use asyncio.run safely.
    import asyncio

    async def _run():
        return await SruClient().search(
            req.cql,
            start_record=req.start_record,
            maximum_records=req.maximum_records,
            record_schema="MARC21-xml",
        )

    try:
        res = asyncio.run(_run())
    except RuntimeError:
        # If running in existing loop (unlikely in uvicorn sync), fallback:
        res = asyncio.get_event_loop().run_until_complete(_run())

    hits: list[SearchHit] = []

    for marcxml in res.records:
        try:
            parsed = parse_marcxml_record(marcxml)
        except Exception:
            continue

        # Upsert record
        rec = db.get(Record, parsed.idn)
        if rec is None:
            rec = Record(idn=parsed.idn, title=parsed.title, year=parsed.year, raw_marcxml=parsed.raw_marcxml)
            db.add(rec)
        else:
            rec.title = parsed.title
            rec.year = parsed.year
            rec.raw_marcxml = parsed.raw_marcxml

        db.flush()

        # Upsert links (unique by record_idn + url)
        link_count = 0
        for l in parsed.links:
            existing = (
                db.query(Link)
                .filter(Link.record_idn == parsed.idn)
                .filter(Link.url == l.url)
                .one_or_none()
            )
            if existing is None:
                db.add(
                    Link(
                        record_idn=parsed.idn,
                        url=l.url,
                        label=l.label,
                        description=l.description,
                        kind=l.kind,
                    )
                )
            else:
                existing.label = l.label
                existing.description = l.description
                existing.kind = l.kind
            link_count += 1

        hits.append(
            SearchHit(
                idn=parsed.idn,
                title=parsed.title,
                year=parsed.year,
                creators=parsed.creators,
                links_count=link_count,
            )
        )

    db.commit()
    return SearchResponse(number_of_records=res.number_of_records, hits=hits)


@router.get("/records/{idn}", response_model=RecordResponse)
def get_record(idn: str, db: Session = Depends(get_db)) -> RecordResponse:
    rec = db.get(Record, idn)
    if rec is None:
        raise HTTPException(status_code=404, detail="Record not found")

    links = (
        db.query(Link)
        .filter(Link.record_idn == idn)
        .order_by(Link.created_at.asc())
        .all()
    )

    return RecordResponse(
        idn=rec.idn,
        title=rec.title,
        year=rec.year,
        creators=[],  # We don't persist creators separately in MVP
        links=[
            LinkOut(id=l.id, url=l.url, label=l.label, description=l.description, kind=l.kind)
            for l in links
        ],
    )


@router.post("/records/{idn}/ingest", response_model=IngestResponse)
def ingest_record(idn: str, req: IngestRequest, db: Session = Depends(get_db)) -> IngestResponse:
    rec = db.get(Record, idn)
    if rec is None:
        raise HTTPException(status_code=404, detail="Record not found")

    q = db.query(Link).filter(Link.record_idn == idn)
    if req.link_ids:
        q = q.filter(Link.id.in_(req.link_ids))
    links = q.all()
    if not links:
        raise HTTPException(status_code=400, detail="No links selected")

    job = Job(status="running")
    db.add(job)
    db.flush()

    assets: list[Asset] = []
    for link in links:
        asset = Asset(link_id=link.id, status="queued")
        db.add(asset)
        db.flush()
        db.add(JobItem(job_id=job.id, asset_id=asset.id))
        assets.append(asset)

    db.commit()

    # Enqueue downloads
    for asset in assets:
        celery_app.send_task("ingest_asset", args=[asset.id])

    return IngestResponse(
        job_id=job.id,
        assets=[
            AssetOut(
                id=a.id,
                link_id=a.link_id,
                status=a.status,
                storage_key=a.storage_key,
                sha256=a.sha256,
                mime_type=a.mime_type,
                size_bytes=a.size_bytes,
                error=a.error,
            )
            for a in assets
        ],
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    asset_ids = [item.asset_id for item in job.items]
    if asset_ids:
        rows = db.query(Asset.status).filter(Asset.id.in_(asset_ids)).all()
        statuses = [s for (s,) in rows]
        if statuses and all(s in {"done", "failed"} for s in statuses):
            if job.status != "completed":
                job.status = "completed"
                db.commit()

    return JobResponse(id=job.id, status=job.status, asset_ids=asset_ids)


@router.get("/assets/{asset_id}/presign")
def presign_asset(asset_id: str, db: Session = Depends(get_db)) -> dict:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.status != "done" or not asset.storage_key:
        raise HTTPException(status_code=400, detail="Asset not available")

    client = get_minio_client()
    url = client.presigned_get_object(
        bucket_name=settings.s3_bucket,
        object_name=asset.storage_key,
        expires=timedelta(minutes=15),
    )
    return {"url": url, "expires_minutes": 15}
