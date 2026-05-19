# -*- coding: utf-8 -*-
"""Tool-profile definitions for constrained tool surfaces."""

from __future__ import annotations

import os
from typing import Optional, Tuple


TOOL_PROFILE_ENV_VAR = "DJX_TOOL_PROFILE"

HARNESS_TOOL_GROUPS: Tuple[str, ...] = (
    "apply",
    "context",
    "retrieve",
    "plan",
)
# Tools that live inside HARNESS_TOOL_GROUPS but are still hidden from
# the harness profile. Tools outside HARNESS_TOOL_GROUPS are already
# filtered out by group selection and do not need to be listed here.
HARNESS_EXCLUDED_TOOL_NAMES: Tuple[str, ...] = (
    "retrieve_operators_api",
)

_UNRESTRICTED_PROFILES = {"", "all", "core", "default", "full"}
_KNOWN_PROFILES = _UNRESTRICTED_PROFILES | {"harness"}


def normalize_tool_profile(profile: str | None) -> str:
    value = str(profile or "").strip().lower()
    if value in _UNRESTRICTED_PROFILES:
        return "default"
    if value == "harness":
        return value
    raise ValueError(
        f"unsupported tool profile: {profile!r}; expected one of {sorted(_KNOWN_PROFILES)}"
    )


def get_active_tool_profile() -> str:
    return normalize_tool_profile(os.environ.get(TOOL_PROFILE_ENV_VAR))


def groups_for_tool_profile(profile: str | None) -> Tuple[str, ...] | None:
    normalized = normalize_tool_profile(profile)
    if normalized == "default":
        return None
    if normalized == "harness":
        return HARNESS_TOOL_GROUPS
    raise ValueError(f"unsupported tool profile: {profile!r}")


def tool_is_excluded_from_profile(tool_name: str, profile: str | None) -> bool:
    normalized = normalize_tool_profile(profile)
    name = str(tool_name or "").strip()
    if normalized == "harness":
        return name in HARNESS_EXCLUDED_TOOL_NAMES
    return False


__all__ = [
    "HARNESS_EXCLUDED_TOOL_NAMES",
    "HARNESS_TOOL_GROUPS",
    "TOOL_PROFILE_ENV_VAR",
    "get_active_tool_profile",
    "groups_for_tool_profile",
    "normalize_tool_profile",
    "tool_is_excluded_from_profile",
]
