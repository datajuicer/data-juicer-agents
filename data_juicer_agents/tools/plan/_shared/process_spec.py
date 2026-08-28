# -*- coding: utf-8 -*-
"""Shared process-spec helpers for plan tools."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .normalize import normalize_params
from .schema import ProcessOperator, ProcessSpec


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
    """Validate process spec structure and operator names via DJ preflight.

    Structural checks (empty operators, missing names, non-dict params) are
    performed here. Operator name existence, parameter name validity, and
    parameter type checking are delegated to DJ's pre_instantiation_check
    which provides fuzzy-match suggestions.
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

    # Skip DJ preflight if structural errors already found
    if errors:
        return errors, warnings

    # Delegate op name + param validation to DJ's preflight module
    try:
        from data_juicer.core.preflight import (
            PipelineConfigError,
            pre_instantiation_check,
        )
    except ImportError:
        warnings.append(
            "operator name/param validation skipped: DJ preflight unavailable"
        )
        return errors, warnings

    try:
        process_list = [
            {op.name: op.params if op.params else None}
            for op in process_spec.operators
            if op.name
        ]
        pre_instantiation_check(process_list)
    except PipelineConfigError as exc:
        for err in exc.errors:
            errors.append(str(err))
    except Exception:
        warnings.append(
            "operator name/param validation skipped: DJ preflight unavailable"
        )

    return errors, warnings


__all__ = [
    "normalize_process_spec",
    "validate_process_spec_payload",
]
