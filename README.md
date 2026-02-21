# DNB Knowledge Base (FastAPI + Worker)

This is an **Option B** starter scaffold:
- **FastAPI** backend to query DNB SRU (CQL) and persist records + links
- **Celery worker** to download linked content and store it in **MinIO (S3 compatible)**
- **PostgreSQL** for metadata + job state

> Note: `location=onlinefree` is a discovery filter, not a rights guarantee. Treat downloaded content as potentially subject to third‑party rights.

## Quickstart

```bash
docker compose up --build
```

- API: `http://localhost:8000/docs`
- RabbitMQ UI: `http://localhost:15672` (guest/guest)
- MinIO Console: `http://localhost:9001` (minioadmin/minioadmin)

## Try it

### 1) Search

Open Swagger UI (`/docs`) and call `POST /search` with e.g.:

```json
{
  "cql": "tit=mittelalter* and location=onlinefree",
  "start_record": 1,
  "maximum_records": 10
}
```

This stores:
- the MARCXML record (raw)
- a simplified record row (`idn`, `title`, `year`)
- extracted links from MARC field 856 (`$u`, with `$3/$y` as label/description)

### 2) Inspect a record

`GET /records/{idn}`

### 3) Ingest links (download)

`POST /records/{idn}/ingest`

Optionally restrict to certain link IDs:

```json
{ "link_ids": ["<uuid>"] }
```

This will:
- create `assets` rows
- enqueue Celery jobs
- worker downloads and uploads into MinIO bucket `dnbkb` under key `{idn}/{asset_id}`

### 4) Get a presigned download URL

`GET /assets/{asset_id}/presign`

## Next steps (recommended sprint order)

1. **Make /search incremental & paginated**: save the original query as a "collection" and page through SRU (`startRecord`, `maximumRecords`).
2. **Text extraction pipeline**: add Apache Tika or pdfminer for PDF -> text, store text chunks, and compute embeddings (pgvector).
3. **OpenWebUI-style chat**: expose an OpenAI-compatible `/v1/chat/completions` endpoint that retrieves chunks from your DB and cites assets.
4. **Hardening**: stricter SSRF/redirect rules, per-domain throttles, user auth, quotas.

## Development notes

- Tables are auto-created on startup (MVP). Replace with Alembic migrations when schema stabilizes.
- The worker blocks private/loopback/link-local destinations (basic SSRF control). Tighten as needed.
