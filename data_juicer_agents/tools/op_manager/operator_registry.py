# -*- coding: utf-8 -*-
"""Operator registry utilities backed by installed Data-Juicer metadata."""

from __future__ import annotations

import re
from difflib import get_close_matches
from functools import lru_cache
from typing import Dict, Iterable, Optional, Set


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@lru_cache(maxsize=1)
def get_available_operator_names() -> Set[str]:
    """Return installed Data-Juicer operator names.

    Empty set means metadata is currently unavailable.
    """

    try:
        from data_juicer_agents.tools.op_manager.op_retrieval import (
            get_dj_func_info,
            init_dj_func_info,
        )

        init_dj_func_info()
        info = get_dj_func_info()
        return {
            str(item.get("class_name", "")).strip()
            for item in info
            if isinstance(item, dict) and str(item.get("class_name", "")).strip()
        }
    except Exception:
        return set()


def _normalize_operator_name(name: str) -> str:
    return _NON_ALNUM_RE.sub("", str(name or "").strip().lower())


def resolve_operator_name(
    name: str,
    available_ops: Optional[Iterable[str]] = None,
) -> str:
    """Resolve a model-produced operator name to installed canonical name.

    Resolution strategy is generic (not workflow-specific):
    1) Exact match.
    2) Case-insensitive match.
    3) Alnum-normalized match (e.g. DocumentMinHashDeduplicator ->
       document_minhash_deduplicator).
    4) Closest normalized match with a strict similarity cutoff.
    """

    raw = str(name or "").strip()
    if not raw:
        return raw

    ops = set(available_ops or get_available_operator_names())
    if not ops:
        return raw

    if raw in ops:
        return raw

    lowered = raw.lower()
    lower_map: Dict[str, str] = {op.lower(): op for op in ops}
    if lowered in lower_map:
        return lower_map[lowered]

    normalized_raw = _normalize_operator_name(raw)
    normalized_map: Dict[str, str] = {}
    for op in ops:
        key = _normalize_operator_name(op)
        if key and key not in normalized_map:
            normalized_map[key] = op
    if normalized_raw in normalized_map:
        return normalized_map[normalized_raw]

    if normalized_raw:
        candidates = get_close_matches(
            normalized_raw,
            list(normalized_map.keys()),
            n=1,
            cutoff=0.93,
        )
        if candidates:
            return normalized_map[candidates[0]]

    return raw
