# -*- coding: utf-8 -*-
"""Scan custom operator paths and build retrieval-compatible candidate metadata.

Used by PlanOrchestrator to inject custom operators into the retrieval
candidate list so the LLM planner can select them.

This module is **metadata-only**: it assumes operators have already been
registered into the DJ global registry (via ``register_custom_operators``).
It reads the registry + ``OPSearcher`` to produce candidate dicts.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Dict, List, Sequence

from data_juicer_agents.utils.dj_config_bridge import (
    create_op_searcher,
    get_builtin_operator_names,
)

logger = logging.getLogger(__name__)

# Maximum number of __init__ params to include in the candidate preview.
# ``None`` means no limit; set to a positive int to truncate.
_MAX_PREVIEW_PARAMS: int | None = None


def _extract_init_params_from_class(cls: type) -> List[str]:
    """Extract __init__ parameter names via inspect (includes inherited params)."""
    try:
        sig = inspect.signature(cls.__init__)
        params = [
            name
            for name, param in sig.parameters.items()
            if name != "self"
            and param.kind not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
        ]
        return params[:_MAX_PREVIEW_PARAMS] if _MAX_PREVIEW_PARAMS is not None else params
    except (ValueError, TypeError):
        return []


def scan_custom_operators(
    registered_operator_names: Sequence[str] | None = None,
) -> List[Dict[str, Any]]:
    """Build candidate-format metadata for already-registered custom operators.

    This function does **not** load or register operators itself — that is
    the responsibility of ``register_custom_operators``.  It only reads
    the DJ registry to produce candidate dicts compatible with the
    retrieval payload format.

    Args:
        registered_operator_names: Explicit list of custom operator names
            (as returned by ``register_custom_operators``).  When provided,
            the registry diff is skipped entirely.  When ``None``, falls
            back to diffing the registry against the builtin snapshot.

    Returns:
        List of candidate dicts compatible with the retrieval payload format.
    """
    # Determine which operator names to scan
    if registered_operator_names is not None:
        custom_op_names = sorted(registered_operator_names)
    else:
        # Fallback: diff registry against builtin snapshot
        try:
            from data_juicer.ops import OPERATORS
        except ImportError:
            logger.warning("data_juicer.ops not available; skipping custom operator scan")
            return []
        builtin_names = get_builtin_operator_names()
        custom_op_names = sorted(set(OPERATORS.modules.keys()) - builtin_names)

    if not custom_op_names:
        return []

    # Ensure OPERATORS is available for class lookup
    try:
        from data_juicer.ops import OPERATORS
    except ImportError:
        logger.warning("data_juicer.ops not available; skipping custom operator scan")
        return []

    # Use OPSearcher to get rich metadata (type, desc, params, tags)
    try:
        searcher = create_op_searcher()
        all_ops = searcher.all_ops
    except Exception as exc:
        logger.warning("OPSearcher unavailable, falling back to registry: %s", exc)
        all_ops = None

    candidates = []
    for rank, op_name in enumerate(custom_op_names, start=1):
        if op_name not in OPERATORS.modules:
            logger.warning("Operator %s not found in registry; skipping", op_name)
            continue

        if all_ops is not None and op_name in all_ops:
            record = all_ops[op_name]
            operator_type = getattr(record, "type", "unknown")
            description = getattr(record, "desc", "") or ""
            source_file = getattr(record, "source_path", "") or ""
            arguments_preview = _extract_init_params_from_class(
                OPERATORS.modules[op_name]
            )
        else:
            cls = OPERATORS.modules[op_name]
            operator_type = _infer_type_from_bases(cls)
            description = (cls.__doc__ or "").split("\n")[0].strip()
            try:
                source_file = inspect.getfile(cls)
            except (TypeError, OSError):
                source_file = ""
            arguments_preview = _extract_init_params_from_class(cls)

        candidates.append({
            "rank": rank,
            "operator_name": op_name,
            "operator_type": operator_type,
            "description": description,
            "relevance_score": 1.0,
            "score_source": "custom_operator",
            "key_match": [],
            "arguments_preview": arguments_preview,
            "is_custom": True,
            "source_file": source_file,
        })

    return candidates


def _infer_type_from_bases(cls: type) -> str:
    """Infer operator type from class inheritance hierarchy (best-effort).

    Uses class name matching against the MRO, which works for standard
    DJ base classes but may misidentify user classes that happen to share
    names like ``Mapper`` or ``Filter`` with unrelated hierarchies.
    Prefer ``OPSearcher`` metadata when available.
    """
    base_names = {base.__name__ for base in cls.__mro__}
    if "Mapper" in base_names:
        return "mapper"
    if "Filter" in base_names:
        return "filter"
    if "Deduplicator" in base_names:
        return "deduplicator"
    if "Aggregator" in base_names:
        return "aggregator"
    if "Selector" in base_names:
        return "selector"
    if "Grouper" in base_names:
        return "grouper"
    return "unknown"


__all__ = ["scan_custom_operators"]
