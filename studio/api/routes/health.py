# -*- coding: utf-8 -*-
"""Health check routes."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict[str, object]:
    return {"ok": True}


__all__ = ["router"]
