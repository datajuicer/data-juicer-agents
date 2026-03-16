# -*- coding: utf-8 -*-
"""Shared system-spec helpers for plan tools."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from .._shared.schema import SystemSpec

SYSTEM_SPEC_DEFERRED_WARNING = (
    "system spec inference deferred; using deterministic minimal profile"
)


def _normalize_string_list(values: Iterable[Any] | None) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for item in values or []:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def normalize_system_spec(
    system_spec: SystemSpec | Dict[str, Any] | None,
    *,
    custom_operator_paths: Iterable[Any] | None = None,
) -> SystemSpec:
    if isinstance(system_spec, SystemSpec):
        source = system_spec
    elif isinstance(system_spec, dict):
        source = SystemSpec.from_dict(system_spec)
    elif system_spec is None:
        source = SystemSpec()
    else:
        raise ValueError("system_spec must be a dict object")

    warnings = _normalize_string_list(source.warnings)
    if SYSTEM_SPEC_DEFERRED_WARNING not in warnings:
        warnings.append(SYSTEM_SPEC_DEFERRED_WARNING)

    return SystemSpec(
        executor_type=str(source.executor_type or "default").strip() or "default",
        np=max(int(source.np or 1), 1),
        open_tracer=bool(source.open_tracer),
        open_monitor=source.open_monitor if isinstance(source.open_monitor, bool) else None,
        use_cache=source.use_cache if isinstance(source.use_cache, bool) else None,
        skip_op_error=bool(source.skip_op_error),
        custom_operator_paths=(
            _normalize_string_list(custom_operator_paths)
            or _normalize_string_list(source.custom_operator_paths)
        ),
        warnings=warnings,
    )


def validate_system_spec_payload(system_spec: SystemSpec | Dict[str, Any]) -> Tuple[List[str], List[str]]:
    if isinstance(system_spec, dict):
        system_spec = SystemSpec.from_dict(system_spec)
    errors: List[str] = []
    warnings: List[str] = []
    if not system_spec.executor_type:
        errors.append("executor_type is required")
    if int(system_spec.np or 0) <= 0:
        errors.append("np must be >= 1")
    if SYSTEM_SPEC_DEFERRED_WARNING not in system_spec.warnings:
        warnings.append(SYSTEM_SPEC_DEFERRED_WARNING)
    warnings.extend([item for item in system_spec.warnings if item and item not in warnings])
    return errors, warnings


__all__ = [
    "SYSTEM_SPEC_DEFERRED_WARNING",
    "normalize_system_spec",
    "validate_system_spec_payload",
]
