# -*- coding: utf-8 -*-
"""FastAPI application assembly for DJX Studio API."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from studio.api.routes.health import router as health_router
from studio.api.routes.session import router as session_router
from studio.api.routes.settings import router as settings_router
from studio.api.routes.workspace import router as workspace_router


def _build_cors_origins() -> list[str]:
    raw = os.environ.get("DJX_UI_CORS_ORIGINS", "").strip()
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


app = FastAPI(title="DJX UI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(settings_router)
app.include_router(session_router)
app.include_router(workspace_router)


__all__ = ["app"]
