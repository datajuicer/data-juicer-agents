# -*- coding: utf-8 -*-
"""Pure logic for register_custom_operators.

Loads custom operator modules into the DJ OPERATORS registry so that
downstream tools (``retrieve_operators``, ``build_process_spec``, etc.)
can discover and validate them.

This is the **single authoritative registration entry-point** used by
both the session (soft-orchestration) and plan (hard-orchestration)
pipelines.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from data_juicer_agents.utils.dj_config_bridge import (
    get_builtin_operator_names,
    load_custom_operators_into_registry,
)

logger = logging.getLogger(__name__)


def register_custom_operators(
    *,
    paths: List[str],
) -> Dict[str, Any]:
    """Register custom operators into the DJ global registry.

    Args:
        paths: Directory or ``.py`` file paths containing custom operators
            decorated with ``@OPERATORS.register_module``.

    Returns:
        Dict with keys ``ok``, ``registered_operators``, ``warnings``,
        and ``message``.
    """
    clean_paths = [p.strip() for p in paths if p.strip()]
    if not clean_paths:
        return {
            "ok": False,
            "error_type": "missing_required",
            "registered_operators": [],
            "warnings": [],
            "message": "custom_operator_paths must contain at least one non-empty path",
        }

    # Snapshot builtin names before loading (idempotent)
    builtin_names = get_builtin_operator_names()

    # Snapshot current custom operators before loading to detect new ones
    try:
        from data_juicer.ops import OPERATORS

        pre_load_names = set(OPERATORS.modules.keys())
    except ImportError:
        return {
            "ok": False,
            "error_type": "dj_unavailable",
            "registered_operators": [],
            "warnings": ["Data-Juicer is not installed; cannot register operators"],
            "message": "Data-Juicer is not available",
        }

    # Load custom operators into the global registry
    load_warnings = load_custom_operators_into_registry(clean_paths)

    # Diff registry to find all custom operators and newly added ones
    post_load_names = set(OPERATORS.modules.keys())
    all_custom_names = sorted(post_load_names - builtin_names)
    newly_registered = sorted(post_load_names - pre_load_names)

    if load_warnings:
        for w in load_warnings:
            logger.warning("register_custom_operators: %s", w)

    # Only refresh the retrieval catalog when new operators were actually added
    if newly_registered:
        try:
            from data_juicer_agents.tools.retrieve._shared.backend import (
                refresh_op_catalog,
            )

            refresh_op_catalog()
        except Exception as exc:
            refresh_warning = f"Failed to refresh op_catalog after registration: {exc}"
            logger.warning(refresh_warning)
            load_warnings.append(refresh_warning)

    # Build a clear message distinguishing new vs already-registered
    if newly_registered:
        message = (
            f"Registered {len(newly_registered)} new custom operator(s): "
            + ", ".join(newly_registered)
        )
    elif all_custom_names:
        message = (
            f"{len(all_custom_names)} custom operator(s) already registered: "
            + ", ".join(all_custom_names)
        )
    else:
        message = "No custom operators found in the provided paths"

    # If warnings were raised and no operators were registered at all,
    # the load effectively failed — report ok=False so callers don't
    # silently proceed with an empty operator set.
    success = bool(all_custom_names) or not load_warnings

    return {
        "ok": success,
        "registered_operators": all_custom_names,
        "newly_registered": newly_registered,
        "warnings": load_warnings,
        "message": message,
    }


__all__ = ["register_custom_operators"]
