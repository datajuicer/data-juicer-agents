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
        from data_juicer_agents.utils.dj_config_bridge import get_dj_config_bridge

        bridge = get_dj_config_bridge()

        # Get all system config fields with defaults
        system_config = bridge.extract_system_config()

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
        
        
        return {
            "ok": True,
            "message": f"Listed {len(config)} system configuration parameters",
            "config": config,
            "total_count": len(config),
            "filter_applied": filter_prefix,
        }
        
    except Exception as e:
        return {
            "ok": False,
            "message": f"Failed to list system config: {str(e)}",
            "config": {},
            "total_count": 0,
            "filter_applied": filter_prefix,
        }

__all__ = ["list_system_config"]
