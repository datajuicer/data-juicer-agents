# -*- coding: utf-8 -*-
"""Shared system-spec helpers for plan tools."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from .._shared.schema import SystemSpec

SYSTEM_SPEC_DEFERRED_WARNING = ""


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

    # Build normalized spec dict with all fields
    normalized_dict = {
        "executor_type": str(source.executor_type or "default").strip() or "default",
        "np": max(int(source.np or 1), 1),
        "custom_operator_paths": (
            _normalize_string_list(custom_operator_paths)
            or _normalize_string_list(source.custom_operator_paths)
        ),
        "warnings": warnings,
    }
    
    # Add all extra fields from source
    source_dict = source.to_dict()
    for key, value in source_dict.items():
        if key not in normalized_dict:
            normalized_dict[key] = value
    
    return SystemSpec.from_dict(normalized_dict)


def validate_system_spec_payload(system_spec: SystemSpec | Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Validate system spec using Data-Juicer's native validation when possible."""
    if isinstance(system_spec, dict):
        system_spec = SystemSpec.from_dict(system_spec)
    
    errors: List[str] = []
    warnings: List[str] = []
    
    # Basic validation for core fields
    if not system_spec.executor_type:
        errors.append("executor_type is required")
    if int(system_spec.np or 0) <= 0:
        errors.append("np must be >= 1")
    
    # Try to use Data-Juicer's native validation
    try:
        from data_juicer_agents.utils.dj_config_bridge import validate_system_config
        
        system_dict = system_spec.to_dict()
        # Remove non-DJ fields before validation (warnings is our internal field)
        dj_dict = {k: v for k, v in system_dict.items() if k != 'warnings'}
        is_valid, dj_errors = validate_system_config(dj_dict)
        
        if not is_valid:
            errors.append(dj_errors)
    except Exception:
        # Fallback to basic validation if DJ validation fails
        pass
    
    # Add deferred warning if not present
    if SYSTEM_SPEC_DEFERRED_WARNING not in system_spec.warnings:
        warnings.append(SYSTEM_SPEC_DEFERRED_WARNING)
    warnings.extend([item for item in system_spec.warnings if item and item not in warnings])
    
    return errors, warnings


__all__ = [
    "SYSTEM_SPEC_DEFERRED_WARNING",
    "normalize_system_spec",
    "validate_system_spec_payload",
]
