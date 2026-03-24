# -*- coding: utf-8 -*-
"""Pure logic for list_system_config."""

from __future__ import annotations

from typing import Any, Dict, Optional

def list_system_config(
    *,
    filter_prefix: Optional[str] = None,
    include_descriptions: bool = True
) -> Dict[str, Any]:
    """List system configuration from Data-Juicer.
    
    This function lists all available system configuration parameters
    from Data-Juicer, including their types, default values, and descriptions.
    
    Args:
        filter_prefix: Optional filter to show only parameters matching this prefix
        include_descriptions: Whether to include parameter descriptions
        
    Returns:
        Dict containing configuration information and available parameters
    """
    try:
        from data_juicer_agents.utils.dj_config_bridge import (
            agent_managed_fields,
            dataset_fields,
            get_dj_config_bridge,
            system_fields,
        )

        bridge = get_dj_config_bridge()

        # Get all system config fields with defaults (based on explicit system_fields list)
        system_config = bridge.extract_system_config()

        # Detect unclassified fields: fields in DJ parser but not in any known category.
        # This happens when the upstream Data-Juicer adds new config fields that we
        # haven't categorised yet.
        all_parser_fields = set(bridge.get_default_config().keys())
        classified_fields = (
            set(system_fields) | set(dataset_fields) | set(agent_managed_fields) | {"process"}
        )
        unclassified_fields = sorted(all_parser_fields - classified_fields)

        warnings = []
        if unclassified_fields:
            warnings.append(
                f"The following {len(unclassified_fields)} DJ config field(s) are not yet "
                f"classified into system/dataset/agent-managed categories and have been "
                f"excluded from the listing: {unclassified_fields}"
            )

        # Get descriptions if requested
        descriptions = {}
        if include_descriptions:
            all_descriptions = bridge.get_param_descriptions()
            # Filter to only system config fields
            descriptions = {
                k: v for k, v in all_descriptions.items() if k in system_config
            }
        
        # Build config for each parameter
        config = {}
        for param_name, default_value in system_config.items():
            # Apply prefix filter if specified
            if filter_prefix and not param_name.startswith(filter_prefix):
                continue
            
            param_info = {
                "default": default_value,
                "type": type(default_value).__name__ if default_value is not None else "None",
            }
            
            if include_descriptions and param_name in descriptions:
                param_info["description"] = descriptions[param_name]
            
            config[param_name] = param_info
        
        result = {
            "ok": True,
            "message": f"Listed {len(config)} system configuration parameters",
            "config": config,
            "total_count": len(config),
            "filter_applied": filter_prefix,
        }
        if warnings:
            result["warnings"] = warnings
        return result
        
    except Exception as e:
        return {
            "ok": False,
            "message": f"Failed to list system config: {str(e)}",
            "config": {},
            "total_count": 0,
            "filter_applied": filter_prefix,
        }

__all__ = ["list_system_config"]
