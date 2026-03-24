# -*- coding: utf-8 -*-
"""Shared process-spec helpers for plan tools."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .normalize import normalize_params
from .schema import ProcessOperator, ProcessSpec

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

    spec = ProcessSpec(operators=operators)
    if not spec.operators:
        raise ValueError("process_spec.operators must contain at least one operator")
    return spec


def validate_process_spec_payload(
    process_spec: ProcessSpec | Dict[str, Any],
) -> Tuple[List[str], List[str]]:
    """Validate process spec structure and operator names/params via DJ bridge."""
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

    # DJ bridge validation (two steps)
    try:
        from data_juicer_agents.utils.dj_config_bridge import get_dj_config_bridge

        bridge = get_dj_config_bridge()

        # Step 1: op_registry validation (dj-agents-side business logic)
        # ProcessSpec structure is natural for this: use op.name / op.params directly
        op_names = {op.name for op in process_spec.operators if op.name}
        op_param_map, known_op_names = bridge.get_op_valid_params(op_names)
        for idx, op in enumerate(process_spec.operators):
            if not op.name:
                continue
            if op.name not in known_op_names:
                errors.append(f"operators[{idx}]: unknown operator '{op.name}'")
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
