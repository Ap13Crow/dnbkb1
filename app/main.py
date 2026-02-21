from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.db.init_db import init_db


def create_app() -> FastAPI:
    init_db()

    app = FastAPI(title="DNB Knowledge Base API", version="0.1.0")

    # Dev-friendly CORS (tighten in production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"] ,
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


app = create_app()
