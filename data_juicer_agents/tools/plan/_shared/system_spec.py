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
    """Normalize system spec, preserving all dynamic fields from Data-Juicer."""
    # Convert to SystemSpec if needed (from_dict handles all dynamic fields)
    if isinstance(system_spec, SystemSpec):
        spec = system_spec
    elif isinstance(system_spec, dict):
        spec = SystemSpec.from_dict(system_spec)
    elif system_spec is None:
        spec = SystemSpec()
    else:
        raise ValueError("system_spec must be a dict object")

    # Inject deferred warning if not present
    if SYSTEM_SPEC_DEFERRED_WARNING not in spec.warnings:
        spec.warnings.append(SYSTEM_SPEC_DEFERRED_WARNING)

    # Override custom_operator_paths if provided externally
    if custom_operator_paths is not None:
        spec.custom_operator_paths = _normalize_string_list(custom_operator_paths)

    return spec


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
            errors.extend(dj_errors)
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
