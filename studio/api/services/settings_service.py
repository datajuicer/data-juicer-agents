# -*- coding: utf-8 -*-
"""Business logic for frontend settings API."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

import httpx

from studio.api.models.settings import SettingsProfilePublic
from studio.api.repositories.settings_repository import mask_api_key


def merge_profile(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key in (
        "dashscope_api_key",
        "session_model",
        "planner_model",
        "validator_model",
        "thinking",
        "base_url",
    ):
        if key not in patch:
            continue
        value = patch[key]
        if value is None:
            continue
        if key == "thinking":
            merged[key] = bool(value)
        else:
            merged[key] = str(value).strip()
    return merged


def _extract_models(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    items = payload.get("data", [])
    if not isinstance(items, list):
        return []

    models: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id", "")).strip()
        if model_id:
            models.append(model_id)
    return models


def test_connection(profile: dict[str, Any], timeout_seconds: float = 10.0) -> dict[str, Any]:
    api_key = str(profile.get("dashscope_api_key", "")).strip()
    if not api_key:
        return {
            "ok": False,
            "endpoint": "",
            "message": "Missing API key in profile.",
            "status_code": None,
            "models": [],
        }

    base_url = str(profile.get("base_url", "")).strip().rstrip("/")
    if not base_url:
        return {
            "ok": False,
            "endpoint": "",
            "message": "Missing base_url in profile.",
            "status_code": None,
            "models": [],
        }

    endpoint = f"{base_url}/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.get(endpoint, headers=headers, timeout=timeout_seconds)
    except Exception as exc:
        return {
            "ok": False,
            "endpoint": endpoint,
            "message": f"Connection failed: {exc}",
            "status_code": None,
            "models": [],
        }

    payload: Any = {}
    try:
        payload = response.json()
    except Exception:
        payload = {}

    if response.status_code >= 400:
        message = "Connection failed"
        if isinstance(payload, dict):
            error_obj = payload.get("error")
            if isinstance(error_obj, dict):
                msg = str(error_obj.get("message", "")).strip()
                if msg:
                    message = msg
        return {
            "ok": False,
            "endpoint": endpoint,
            "message": message,
            "status_code": response.status_code,
            "models": [],
        }

    models = _extract_models(payload)
    return {
        "ok": True,
        "endpoint": endpoint,
        "message": "Connection successful.",
        "status_code": response.status_code,
        "models": models[:20],
    }


def to_public_profile(profile: Mapping[str, object]) -> SettingsProfilePublic:
    key = str(profile.get("dashscope_api_key", "") or "").strip()
    return SettingsProfilePublic(
        has_api_key=bool(key),
        dashscope_api_key_masked=mask_api_key(key),
        session_model=str(profile.get("session_model", "") or "").strip(),
        planner_model=str(profile.get("planner_model", "") or "").strip(),
        validator_model=str(profile.get("validator_model", "") or "").strip(),
        thinking=bool(profile.get("thinking", True)),
        base_url=str(profile.get("base_url", "") or "").strip(),
    )
