# -*- coding: utf-8 -*-
"""Input models for list_system_config."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

class ListSystemConfigInput(BaseModel):
    """Input for list_system_config.
    
    This tool lists the complete system configuration from Data-Juicer,
    including all available parameters, their types, default values, and descriptions.
    Use this before build_system_spec to discover available configuration options.
    """
    
    filter_prefix: Optional[str] = Field(
        None,
        description="Optional filter to show only parameters matching this prefix (e.g., 'open_', 'checkpoint')."
    )
    
    include_descriptions: bool = Field(
        True,
        description="Whether to include parameter descriptions. Default is True."
    )
