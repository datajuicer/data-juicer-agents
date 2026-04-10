# -*- coding: utf-8 -*-
"""Scan custom operator paths by importing them into the DJ registry.

Used by PlanOrchestrator to inject custom operators into the retrieval
candidate list so the LLM planner can select them.

Strategy: import the custom operator modules (triggering their
``@OPERATORS.register_module`` decorators), then diff the current
registry against a builtin snapshot to identify custom operators.
Metadata is extracted from ``OPSearcher`` records which provide
accurate type, docstring, init params (including inherited ones),
and tags.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Dict, Iterable, List

logger = logging.getLogger(__name__)

# Maximum number of __init__ params to include in the candidate preview.
# Keeps the LLM prompt concise while still showing the most important params.
_MAX_PREVIEW_PARAMS = -1


def _extract_init_params_from_class(cls: type) -> List[str]:
    """Extract __init__ parameter names via inspect (includes inherited params)."""
    try:
        sig = inspect.signature(cls.__init__)
        return [
            name
            for name, param in sig.parameters.items()
            if name != "self"
            and param.kind not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
        ][:_MAX_PREVIEW_PARAMS]
    except (ValueError, TypeError):
        return []


def scan_custom_operators(
    custom_operator_paths: Iterable[Any] | None,
) -> List[Dict[str, Any]]:
    """Load custom operators and return candidate-format metadata.

    Imports custom operator modules into the DJ registry, then identifies
    custom operators by diffing the current registry against the builtin
    snapshot (captured before any custom operators were loaded).  This
    approach is idempotent and correctly detects name conflicts.

    Args:
        custom_operator_paths: Directories or .py files containing custom
            operators registered via ``@OPERATORS.register_module``.

    Returns:
        List of candidate dicts compatible with the retrieval payload format.
    """
    if not custom_operator_paths:
        return []

    paths = [str(p).strip() for p in custom_operator_paths if str(p).strip()]
    if not paths:
        return []

    # Load custom operators into registry (also captures builtin snapshot)
    from data_juicer_agents.utils.dj_config_bridge import load_custom_operators_into_registry
    load_warnings = load_custom_operators_into_registry(paths)
    for warning in load_warnings:
        logger.warning("Custom operator loading: %s", warning)

    try:
        from data_juicer.ops import OPERATORS
    except ImportError:
        logger.warning("data_juicer.ops not available; skipping custom operator scan")
        return []

    # Diff against builtin snapshot to find custom operators
    from data_juicer_agents.utils.dj_config_bridge import get_builtin_operator_names
    builtin_names = get_builtin_operator_names()
    custom_op_names = sorted(set(OPERATORS.modules.keys()) - builtin_names)

    if not custom_op_names:
        logger.debug("No custom operators registered from paths: %s", paths)
        return []

    # Use OPSearcher to get rich metadata (type, desc, params, tags)
    try:
        from data_juicer.tools.op_search import OPSearcher
        searcher = OPSearcher()
        all_ops = searcher.all_ops
    except Exception as exc:
        logger.warning("OPSearcher unavailable, falling back to registry: %s", exc)
        all_ops = None

    candidates = []
    for rank, op_name in enumerate(custom_op_names, start=1):
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
