# -*- coding: utf-8 -*-
"""Pure logic for build_system_spec."""

from __future__ import annotations

from typing import Any, Dict, Iterable

from .._shared.normalize import normalize_string_list
from .._shared.schema import SystemSpec
from .._shared.system_spec import validate_system_spec_payload

def _load_dj_system_config() -> Dict[str, Any]:
    """Load complete system configuration from Data-Juicer dynamically.
    
    Returns:
        Dict of all system parameters with their default values from DJ
    """
    try:
        from data_juicer_agents.utils.dj_config_bridge import get_dj_config_bridge
        bridge = get_dj_config_bridge()
        return bridge.extract_system_config()
    except Exception:
        # Fallback to minimal defaults if DJ is not available
        return {
            "executor_type": "default",
            "np": 1,
            "open_tracer": False,
            "open_monitor": None,
            "use_cache": None,
            "skip_op_error": False,
        }

def build_system_spec(
    *,
    custom_operator_paths: Iterable[Any] | None = None,
    np: int | None = None,
    executor_type: str | None = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """Build system spec with complete config dynamically loaded from Data-Juicer.
    
    This function now loads ALL system configuration fields from Data-Juicer,
    ensuring automatic sync with any upstream changes.
    
    Args:
        custom_operator_paths: Optional list of custom operator paths
        np: Optional number of processes
        executor_type: Optional executor type
        **kwargs: Any additional system config options (must be valid DJ system
                  config fields — unknown keys will raise ValueError)
        
    Returns:
        Dict containing the built system spec and validation results
    """
    # Load complete system config from Data-Juicer
    dj_system_config = _load_dj_system_config()

    # Override core parameters if provided
    if custom_operator_paths is not None:
        dj_system_config['custom_operator_paths'] = normalize_string_list(custom_operator_paths)

    if np is not None:
        dj_system_config['np'] = np

    if executor_type is not None:
        dj_system_config['executor_type'] = executor_type

    # Merge kwargs
    if kwargs:
        unknown_keys = [k for k in kwargs if k not in dj_system_config]
        if unknown_keys:
            raise ValueError(
                f"Unknown system config field(s): {unknown_keys}. "
                f"Valid fields are: {sorted(dj_system_config.keys())}"
            )
        dj_system_config.update(kwargs)

    # Create SystemSpec from DJ config (dynamically handles all fields)
    spec = SystemSpec.from_dj_config(dj_system_config)

    # Validate using DJ-aware validation
    errors, warnings = validate_system_spec_payload(spec)

    return {
        "ok": len(errors) == 0,
        "system_spec": spec.to_dict(),
        "validation_errors": errors,
        "warnings": warnings,
        "message": "system spec built" if not errors else "system spec build failed",
    }


__all__ = ["build_system_spec"]
