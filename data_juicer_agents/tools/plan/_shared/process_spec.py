# -*- coding: utf-8 -*-
"""Shared process-spec helpers for plan tools."""

from __future__ import annotations

import inspect
import logging
import os
from typing import Any, Dict, Iterable, List, Tuple

from data_juicer_agents.utils.dj_config_bridge import (
    get_builtin_operator_names,
    get_dj_config_bridge,
)

from .normalize import normalize_params
from .schema import ProcessOperator, ProcessSpec

logger = logging.getLogger(__name__)

PROCESS_SPEC_DEFERRED_WARNING = (
    "operator parameter validation deferred; runtime errors will be used as the repair signal"
)


def normalize_process_spec(process_spec: ProcessSpec | Dict[str, Any]) -> ProcessSpec:
    """Normalize process spec: strip names, ensure params are dicts."""
    if isinstance(process_spec, ProcessSpec):
        source = process_spec
    elif isinstance(process_spec, dict):
        source = ProcessSpec.from_dict(process_spec)
    else:
        raise ValueError("process_spec must be a dict object")

    operators: List[ProcessOperator] = []
    for item in source.operators:
        raw_name = str(item.name or "").strip()
        if not raw_name:
            continue
        operators.append(
            ProcessOperator(name=raw_name, params=normalize_params(item.params))
        )

    spec = ProcessSpec(
        operators=operators,
        custom_operator_paths=list(source.custom_operator_paths),
    )
    if not spec.operators:
        raise ValueError("process_spec.operators must contain at least one operator")
    return spec


def validate_process_spec_payload(
    process_spec: ProcessSpec | Dict[str, Any],
    custom_operator_paths: Iterable[Any] | None = None,
) -> Tuple[List[str], List[str]]:
    """Validate process spec structure and operator names/params via DJ bridge.

    Args:
        process_spec: The process spec to validate.
        custom_operator_paths: Optional paths to custom operator directories
            or files.  Used to determine which custom operators are valid
            for this particular plan (source-file ownership check).
            Callers must register custom operators into the DJ registry
            **before** calling this function (via
            ``register_custom_operators``); this function no longer
            performs registration itself.
    """
    if isinstance(process_spec, dict):
        process_spec = ProcessSpec.from_dict(process_spec)

    errors: List[str] = []
    warnings: List[str] = []

    # Basic structural validation
    if not process_spec.operators:
        errors.append("operators must not be empty")
    for idx, op in enumerate(process_spec.operators):
        if not op.name:
            errors.append(f"operators[{idx}].name is required")
        if not isinstance(op.params, dict):
            errors.append(f"operators[{idx}].params must be an object")

    # Build the set of custom op names that are valid for *this* call's
    # custom_operator_paths.  In long-lived sessions the global registry
    # may contain custom ops from earlier calls with different paths;
    # those must NOT pass validation because ``djx apply`` runs in a
    # fresh process that only loads the plan's custom_operator_paths.
    allowed_custom_op_names: set | None = None
    builtin_names: frozenset = frozenset()  # default to empty set if DJ bridge not available
    try:
        builtin_names = get_builtin_operator_names()
        if custom_operator_paths:
            from data_juicer.ops import OPERATORS

            abs_paths = [
                os.path.realpath(str(p).strip())
                for p in custom_operator_paths
                if str(p).strip()
            ]
            allowed_custom_op_names = set()
            all_custom = set(OPERATORS.modules.keys()) - builtin_names
            for name in all_custom:
                cls = OPERATORS.modules[name]
                try:
                    source = os.path.realpath(inspect.getfile(cls))
                except (TypeError, OSError):
                    continue
                for base_path in abs_paths:
                    if source == base_path or source.startswith(base_path + os.sep):
                        allowed_custom_op_names.add(name)
                        break
        else:
            # No custom paths provided — no custom ops are allowed.
            allowed_custom_op_names = set()
    except ImportError:
        # DJ not available; skip custom op filtering
        allowed_custom_op_names = None

    # DJ bridge validation (two steps)
    try:
        bridge = get_dj_config_bridge()

        # Step 1: op_registry validation (dj-agents-side business logic)
        # ProcessSpec structure is natural for this: use op.name / op.params directly
        op_names = {op.name for op in process_spec.operators if op.name}
        op_param_map, known_op_names = bridge.get_op_valid_params(op_names)
        for idx, op in enumerate(process_spec.operators):
            if not op.name:
                continue
            if op.name not in known_op_names:
                errors.append(
                    f"operators[{idx}]: unknown operator '{op.name}'. "
                    f"If this is a custom operator, call register_custom_operators first."
                )
            elif (
                allowed_custom_op_names is not None
                and op.name not in builtin_names
                and op.name not in allowed_custom_op_names
            ):
                errors.append(
                    f"operators[{idx}]: custom operator '{op.name}' is not "
                    f"from the provided custom_operator_paths"
                )
            elif op.name in op_param_map:
                for param_key in (op.params or {}):
                    if param_key not in op_param_map[op.name]:
                        errors.append(
                            f"operators[{idx}].{op.name}: unknown param '{param_key}'"
                        )

    except Exception:
        warnings.append(
            "operator name/param validation skipped: DJ bridge unavailable"
        )

    if PROCESS_SPEC_DEFERRED_WARNING not in warnings:
        warnings.append(PROCESS_SPEC_DEFERRED_WARNING)
    return errors, warnings


__all__ = [
    "PROCESS_SPEC_DEFERRED_WARNING",
    "normalize_process_spec",
    "validate_process_spec_payload",
]
