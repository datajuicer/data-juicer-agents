# -*- coding: utf-8 -*-
"""Shared helpers for building retrieval results and trace entries.

Extracted from backend.py and logic.py to eliminate duplicated code across
the four retrieval backends (LLM, Vector, BM25, Regex).
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Retrieval item builder
# ---------------------------------------------------------------------------

def _sanitize_key_match(key_match: Any) -> list[str]:
    if not isinstance(key_match, list):
        return []
    return [str(k).strip() for k in key_match if str(k).strip()]

def build_retrieval_item(
    tool_name: str,
    description: str = "",
    relevance_score: float = 0.0,
    score_source: str = "",
    operator_type: str = "",
    key_match: list[str] | None = None,
) -> dict[str, Any]:
    """Build a standardised retrieval result item dict.

    All string fields are stripped; ``relevance_score`` is cast to float.
    This is the single authoritative constructor for retrieval items used by
    every backend, replacing the ad-hoc dict literals that were previously
    duplicated across ``retrieve_ops_lm_items``, ``retrieve_ops_bm25_items``,
    and ``retrieve_ops_regex_items``.
    """
    return {
        "tool_name": str(tool_name).strip(),
        "description": str(description).strip(),
        "relevance_score": float(relevance_score),
        "score_source": str(score_source).strip(),
        "operator_type": str(operator_type).strip(),
        "key_match": _sanitize_key_match(key_match),
    }

# ---------------------------------------------------------------------------
# names_from_items helper
# ---------------------------------------------------------------------------

def names_from_items(items: list[dict[str, Any]]) -> list[str]:
    """Extract non-empty tool names from a list of retrieval items.

    Args:
        items: List of retrieval item dicts, each with a ``tool_name`` key.

    Returns:
        List of stripped, non-empty tool names. Empty strings and missing
        keys are silently skipped.
    """
    names: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("tool_name", "")).strip()
        if name:
            names.append(name)
    return names

# ---------------------------------------------------------------------------
# op_type filtering
# ---------------------------------------------------------------------------

def filter_by_op_type(
    info_list: list[dict[str, Any]],
    op_type: str | None,
    type_key: str = "class_type",
) -> list[dict[str, Any]]:
    """Pre-filter an operator info list by *op_type*.

    Falls back to the full list when the filter yields no results, so callers
    always receive a non-empty list as long as *info_list* itself is non-empty.

    Args:
        info_list: List of operator info dicts (e.g. from ``get_op_catalog()``).
        op_type: Operator type string to match (e.g. ``"filter"``).  When
                 ``None`` or empty the full list is returned unchanged.
        type_key: Dict key used to read the operator type from each entry.
    """
    if not op_type:
        return info_list
    filtered = [
        t for t in info_list
        if str(t.get(type_key, "")).strip().lower() == op_type.strip().lower()
    ]
    return filtered if filtered else info_list


def filter_by_tags(
    info_list: list[dict[str, Any]],
    tags: list[str] | None,
    tags_key: str = "class_tags",
) -> list[dict[str, Any]]:
    """Pre-filter an operator info list by *tags* (intersection match).

    An entry matches if its tag set has **any** overlap with the requested
    *tags*.  Falls back to the full list when the filter yields no results,
    consistent with :func:`filter_by_op_type`.

    Args:
        info_list: List of operator info dicts (e.g. from ``get_op_catalog()``).
        tags: Tag strings to match.  When ``None`` or empty the full list is
              returned unchanged.
        tags_key: Dict key used to read the tag list from each entry.
    """
    if not tags:
        return info_list
    expected = {str(t).strip().lower() for t in tags if str(t).strip()}
    if not expected:
        return info_list
    filtered = [
        entry for entry in info_list
        if expected.intersection(
            str(t).strip().lower()
            for t in (entry.get(tags_key) or [])
        )
    ]
    return filtered if filtered else info_list

# ---------------------------------------------------------------------------
# Trace entry builder
# ---------------------------------------------------------------------------

def trace_step(
    backend: str,
    status: str,
    error: str = "",
    reason: str = "",
) -> dict[str, str]:
    """Build a trace entry dict for retrieval diagnostics.

    Args:
        backend: Backend identifier (e.g. ``"llm"``, ``"bm25"``).
        status: Outcome string (e.g. ``"success"``, ``"failed"``, ``"skipped"``).
        error: Optional error message (omitted from output when empty).
        reason: Optional reason string (omitted from output when empty).
    """
    payload: dict[str, str] = {
        "backend": str(backend or "").strip(),
        "status": str(status or "").strip(),
    }
    if e := str(error or "").strip():
        payload["error"] = e
    if r := str(reason or "").strip():
        payload["reason"] = r
    return payload