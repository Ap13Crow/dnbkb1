from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


class Record(Base):
    __tablename__ = "records"

    idn: Mapped[str] = mapped_column(String(64), primary_key=True)  # MARC 001, typically numeric
    title: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_marcxml: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    links: Mapped[list[Link]] = relationship(back_populates="record", cascade="all, delete-orphan")


class Link(Base):
    __tablename__ = "links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    record_idn: Mapped[str] = mapped_column(ForeignKey("records.idn", ondelete="CASCADE"), nullable=False)

    url: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    record: Mapped[Record] = relationship(back_populates="links")
    assets: Mapped[list[Asset]] = relationship(back_populates="link", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("record_idn", "url", name="uq_record_url"),
    )


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    link_id: Mapped[str] = mapped_column(ForeignKey("links.id", ondelete="CASCADE"), nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    link: Mapped[Link] = relationship(back_populates="assets")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items: Mapped[list[JobItem]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobItem(Base):
    __tablename__ = "job_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)

    job: Mapped[Job] = relationship(back_populates="items")

    __table_args__ = (
        UniqueConstraint("job_id", "asset_id", name="uq_job_asset"),
    )
