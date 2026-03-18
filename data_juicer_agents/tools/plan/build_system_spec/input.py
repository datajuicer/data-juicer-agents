# -*- coding: utf-8 -*-
"""Input models for build_system_spec."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

class BuildSystemSpecInput(BaseModel):
    """Input for building system spec.
    
    Core parameters are exposed directly for common use cases.
    All other system parameters can be passed as additional kwargs.
    Use list_system_config tool to discover all available options.
    """
    
    model_config = ConfigDict(extra='allow')  # Allow any additional fields
    
    # Core parameters (most commonly used)
    np: Optional[int] = Field(
        None,
        description="Number of processes to use for dataset processing. Default is 4."
    )
    
    executor_type: Optional[str] = Field(
        None,
        description='Executor type: "default" (single machine), "ray" (distributed), or "ray_partitioned". Default is "default".'
    )
    
    custom_operator_paths: List[str] = Field(
        default_factory=list,
        description="Paths to custom operator modules or packages."
    )
    
    # All other system parameters (open_tracer, use_cache, checkpoint, etc.)
    # can be passed directly as kwargs - they will be validated by DJ bridge