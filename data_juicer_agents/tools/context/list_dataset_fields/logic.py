# -*- coding: utf-8 -*-
"""Pure logic for list_dataset_fields."""

from __future__ import annotations

from typing import Any, Dict, Optional


def list_dataset_fields(
    *,
    filter_prefix: Optional[str] = None,
    include_descriptions: bool = True,
) -> Dict[str, Any]:
    """List dataset-related configuration fields from Data-Juicer.

    This function lists all available dataset configuration parameters
    from Data-Juicer, including their types, default values, and descriptions.

    Args:
        filter_prefix: Optional filter to show only parameters matching this prefix
        include_descriptions: Whether to include parameter descriptions

    Returns:
        Dict containing configuration information and available parameters
    """
    try:
        from data_juicer_agents.utils.dj_config_bridge import (
            dataset_fields,
            get_dj_config_bridge,
        )

        bridge = get_dj_config_bridge()

        # Get all dataset config fields with defaults (based on explicit dataset_fields list)
        dataset_config = bridge.extract_dataset_config()

        # Get descriptions if requested
        descriptions = {}
        if include_descriptions:
            all_descriptions = bridge.get_param_descriptions()
            descriptions = {
                k: v for k, v in all_descriptions.items() if k in dataset_config
            }

        # Build config for each parameter
        config = {}
        for param_name, default_value in dataset_config.items():
            # Apply prefix filter if specified
            if filter_prefix and not param_name.startswith(filter_prefix):
                continue

            param_info: Dict[str, Any] = {
                "default": default_value,
                "type": type(default_value).__name__ if default_value is not None else "None",
            }

            if include_descriptions and param_name in descriptions:
                param_info["description"] = descriptions[param_name]

            config[param_name] = param_info

        result: Dict[str, Any] = {
            "ok": True,
            "message": f"Listed {len(config)} dataset configuration fields",
            "fields": config,
            "total_count": len(config),
            "filter_applied": filter_prefix,
        }
        return result

    except Exception as e:
        return {
            "ok": False,
            "message": f"Failed to list dataset fields: {str(e)}",
            "fields": {},
            "total_count": 0,
            "filter_applied": filter_prefix,
        }


__all__ = ["list_dataset_fields"]
