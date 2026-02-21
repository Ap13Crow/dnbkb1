from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class SearchRequest(BaseModel):
    cql: str = Field(..., description="CQL query for DNB SRU")
    start_record: int = Field(1, ge=1)
    maximum_records: int = Field(10, ge=1, le=100)


class LinkOut(BaseModel):
    id: str
    url: str
    label: str | None = None
    description: str | None = None
    kind: str


class SearchHit(BaseModel):
    idn: str
    title: str | None = None
    year: int | None = None
    creators: list[str] = []
    links_count: int = 0


class SearchResponse(BaseModel):
    number_of_records: int
    hits: list[SearchHit]


class RecordResponse(BaseModel):
    idn: str
    title: str | None = None
    year: int | None = None
    creators: list[str] = []
    links: list[LinkOut] = []


class IngestRequest(BaseModel):
    link_ids: list[str] | None = Field(None, description="If omitted, ingest all links of the record")


class AssetOut(BaseModel):
    id: str
    link_id: str
    status: str
    storage_key: str | None = None
    sha256: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    error: str | None = None


class IngestResponse(BaseModel):
    job_id: str
    assets: list[AssetOut]


class JobResponse(BaseModel):
    id: str
    status: Literal["running", "completed"] | str
    asset_ids: list[str]
