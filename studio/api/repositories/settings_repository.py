# -*- coding: utf-8 -*-
"""Persistent settings store for DJX frontend."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_REL_PATH = Path(".djx") / "config.json"
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3-max-2026-01-23"


def _default_profile() -> dict[str, Any]:
    return {
        "dashscope_api_key": "",
        "session_model": DEFAULT_MODEL,
        "planner_model": DEFAULT_MODEL,
        "validator_model": DEFAULT_MODEL,
        "thinking": True,
        "base_url": DEFAULT_BASE_URL,
    }


def _default_document() -> dict[str, Any]:
    return {
        "version": 1,
        "active_profile": "default",
        "profiles": {
            "default": _default_profile(),
        },
    }


def resolve_config_path() -> Path:
    env_path = os.environ.get("DJX_UI_CONFIG_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser()
    return Path.cwd() / DEFAULT_CONFIG_REL_PATH


def mask_api_key(key: str) -> str | None:
    raw = str(key or "").strip()
    if not raw:
        return None
    if len(raw) <= 8:
        return "*" * len(raw)
    return f"{raw[:4]}***{raw[-4:]}"


class SettingsStore:
    """JSON-backed profile settings store."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or resolve_config_path()

    def load_document(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return _default_document()

        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid config JSON: {exc}") from exc

        return self._normalize_document(data)

    def save_document(self, document: dict[str, Any]) -> None:
        normalized = self._normalize_document(document)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def get_profile(self, profile_name: str | None = None) -> tuple[str, dict[str, Any]]:
        document = self.load_document()
        name = (profile_name or document.get("active_profile") or "default").strip() or "default"
        profiles = document.setdefault("profiles", {})

        if name not in profiles:
            profiles[name] = _default_profile()
            document["active_profile"] = name
            self.save_document(document)

        profile = self._normalize_profile(profiles[name])
        return name, profile

    def update_profile(self, profile_name: str, patch: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        name = (profile_name or "default").strip() or "default"
        document = self.load_document()
        profiles = document.setdefault("profiles", {})

        base = self._normalize_profile(profiles.get(name, {}))
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

        profiles[name] = merged
        document["active_profile"] = name
        self.save_document(document)
        return name, merged

    def _normalize_document(self, raw: dict[str, Any]) -> dict[str, Any]:
        document = _default_document()
        if not isinstance(raw, dict):
            return document

        active_profile = str(raw.get("active_profile", "default") or "default").strip() or "default"
        profiles_in = raw.get("profiles", {})

        profiles_out: dict[str, dict[str, Any]] = {}
        if isinstance(profiles_in, dict):
            for name, profile in profiles_in.items():
                safe_name = str(name).strip()
                if not safe_name:
                    continue
                profiles_out[safe_name] = self._normalize_profile(profile)

        if not profiles_out:
            profiles_out["default"] = _default_profile()

        if active_profile not in profiles_out:
            profiles_out[active_profile] = _default_profile()

        document["active_profile"] = active_profile
        document["profiles"] = profiles_out
        return document

    def _normalize_profile(self, raw: Any) -> dict[str, Any]:
        base = _default_profile()
        if not isinstance(raw, dict):
            return base

        for key in (
            "dashscope_api_key",
            "session_model",
            "planner_model",
            "validator_model",
            "base_url",
        ):
            if key in raw and raw[key] is not None:
                base[key] = str(raw[key]).strip()

        if "thinking" in raw and raw["thinking"] is not None:
            base["thinking"] = bool(raw["thinking"])

        return base
