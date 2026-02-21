from __future__ import annotations

from app.db.base import Base
from app.db.session import engine


def init_db() -> None:
    # MVP: create tables automatically. For production, replace with Alembic migrations.
    Base.metadata.create_all(bind=engine)
