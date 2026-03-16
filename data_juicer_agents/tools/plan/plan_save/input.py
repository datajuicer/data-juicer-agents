# -*- coding: utf-8 -*-
"""Input models for plan_save."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class PlanSaveInput(BaseModel):
    plan_payload: Dict[str, Any] = Field(
        description="Full plan object returned by assemble_plan.",
    )
    output_path: str = Field(description="Target output path for the saved plan YAML file.")
    overwrite: bool = Field(default=False, description="Overwrite the target path if it exists.")
