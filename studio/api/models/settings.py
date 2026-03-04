# -*- coding: utf-8 -*-
"""Settings-related request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsProfilePublic(BaseModel):
    has_api_key: bool = False
    dashscope_api_key_masked: str | None = None
    session_model: str = "qwen3-max-2026-01-23"
    planner_model: str = "qwen3-max-2026-01-23"
    validator_model: str = "qwen3-max-2026-01-23"
    thinking: bool = True
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class SettingsProfileResponse(BaseModel):
    ok: bool = True
    profile_name: str = "default"
    profile: SettingsProfilePublic
    config_path: str


class SettingsProfilePatch(BaseModel):
    dashscope_api_key: str | None = None
    session_model: str | None = None
    planner_model: str | None = None
    validator_model: str | None = None
    thinking: bool | None = None
    base_url: str | None = None


class SettingsProfileUpdateRequest(SettingsProfilePatch):
    profile_name: str = "default"


class ConnectionTestRequest(BaseModel):
    profile_name: str | None = None
    override: SettingsProfilePatch = Field(default_factory=SettingsProfilePatch)


class ConnectionTestResponse(BaseModel):
    ok: bool
    endpoint: str
    message: str
    status_code: int | None = None
    models: list[str] = Field(default_factory=list)


__all__ = [
    "SettingsProfilePublic",
    "SettingsProfileResponse",
    "SettingsProfilePatch",
    "SettingsProfileUpdateRequest",
    "ConnectionTestRequest",
    "ConnectionTestResponse",
]
