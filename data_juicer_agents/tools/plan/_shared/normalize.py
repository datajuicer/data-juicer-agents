# -*- coding: utf-8 -*-
"""Shared normalization utilities for all spec types.

These helpers are used by ``normalize_system_spec``,
``normalize_process_spec``, ``normalize_dataset_spec``, and
``assemble_plan`` to avoid duplicating trivial string/list/dict
sanitisation logic.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def normalize_string_list(values: Iterable[Any] | None) -> List[str]:
    """Deduplicate, strip whitespace, and remove empty strings.

    Preserves insertion order.
    """
    normalized: List[str] = []
    seen: set = set()
    for item in values or []:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def normalize_params(value: Any) -> Dict[str, Any]:
    """Ensure *value* is a ``dict``; return empty dict otherwise."""
    return dict(value) if isinstance(value, dict) else {}


def normalize_optional_text(value: Any) -> Optional[str]:
    """Strip whitespace and return ``None`` if the result is empty."""
    text = str(value or "").strip()
    return text or None


__all__ = [
    "normalize_optional_text",
    "normalize_params",
    "normalize_string_list",
]
