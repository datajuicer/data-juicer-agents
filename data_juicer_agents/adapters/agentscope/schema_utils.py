# -*- coding: utf-8 -*-
"""Utilities for normalizing tool JSON schemas for agent-facing adapters."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


_LOCAL_REF_PREFIXES = ("#/$defs/", "#/definitions/")


def _resolve_local_ref(ref: str, defs: Dict[str, Any]) -> Any:
    for prefix in _LOCAL_REF_PREFIXES:
        if ref.startswith(prefix):
            key = ref[len(prefix) :]
            return deepcopy(defs.get(key))
    return None


def _normalize_node(node: Any, defs: Dict[str, Any], stack: tuple[str, ...]) -> Any:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            resolved = _resolve_local_ref(ref, defs)
            if resolved is not None:
                key = ref.split("/")[-1]
                if key in stack:
                    return {}
                merged = _normalize_node(resolved, defs, stack + (key,))
                extras = {
                    k: v
                    for k, v in node.items()
                    if k not in {"$ref", "$defs", "definitions", "title"}
                }
                if extras:
                    normalized_extras = _normalize_node(extras, defs, stack)
                    if isinstance(merged, dict) and isinstance(normalized_extras, dict):
                        merged.update(normalized_extras)
                    else:
                        return normalized_extras
                return merged

        cleaned: Dict[str, Any] = {}
        for key, value in node.items():
            if key in {"$defs", "definitions", "title"}:
                continue
            cleaned[key] = _normalize_node(value, defs, stack)
        return cleaned
    if isinstance(node, list):
        return [_normalize_node(item, defs, stack) for item in node]
    return node


def normalize_tool_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    raw = deepcopy(schema)
    defs = {}
    for key in ("$defs", "definitions"):
        value = raw.get(key)
        if isinstance(value, dict):
            defs.update(value)
    return _normalize_node(raw, defs, ())


__all__ = ["normalize_tool_schema"]
