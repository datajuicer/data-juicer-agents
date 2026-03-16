# -*- coding: utf-8 -*-
"""Input models for assemble_plan."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class AssemblePlanInput(BaseModel):
    intent: str = Field(description="User intent for the plan.")
    dataset_spec: Dict[str, Any] = Field(
        description="Dataset spec object returned by build_dataset_spec.",
    )
    process_spec: Dict[str, Any] = Field(
        description="Process spec object returned by build_process_spec.",
    )
    system_spec: Dict[str, Any] = Field(
        description="System spec object returned by build_system_spec.",
    )
    approval_required: bool = Field(default=True, description="Whether final apply should require explicit approval.")
