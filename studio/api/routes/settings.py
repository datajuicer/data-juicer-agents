# -*- coding: utf-8 -*-
"""Settings routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from studio.api.deps import get_store
from studio.api.models.settings import (
    ConnectionTestRequest,
    ConnectionTestResponse,
    SettingsProfileResponse,
    SettingsProfileUpdateRequest,
)
from studio.api.repositories.settings_repository import SettingsStore
from studio.api.services.settings_service import (
    merge_profile,
    test_connection,
    to_public_profile,
)

router = APIRouter(tags=["settings"])


@router.get("/api/settings/profile", response_model=SettingsProfileResponse)
def get_settings_profile(
    profile_name: str | None = None,
    store: SettingsStore = Depends(get_store),
) -> SettingsProfileResponse:
    name, profile = store.get_profile(profile_name)
    return SettingsProfileResponse(
        ok=True,
        profile_name=name,
        profile=to_public_profile(profile),
        config_path=str(store.config_path),
    )


@router.put("/api/settings/profile", response_model=SettingsProfileResponse)
def update_settings_profile(
    request: SettingsProfileUpdateRequest,
    store: SettingsStore = Depends(get_store),
) -> SettingsProfileResponse:
    payload = request.model_dump(exclude_none=True)
    name = str(payload.pop("profile_name", "default") or "default").strip() or "default"
    _, profile = store.update_profile(profile_name=name, patch=payload)
    return SettingsProfileResponse(
        ok=True,
        profile_name=name,
        profile=to_public_profile(profile),
        config_path=str(store.config_path),
    )


@router.post("/api/settings/test-connection", response_model=ConnectionTestResponse)
def test_settings_connection(
    request: ConnectionTestRequest,
    store: SettingsStore = Depends(get_store),
) -> ConnectionTestResponse:
    _, profile = store.get_profile(request.profile_name)
    override = request.override.model_dump(exclude_none=True)
    merged = merge_profile(profile, override)
    result = test_connection(merged)
    return ConnectionTestResponse(**result)


__all__ = ["router"]
