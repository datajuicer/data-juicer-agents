# -*- coding: utf-8 -*-
"""Input models for validate_dataset_spec."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class ValidateDatasetSpecInput(BaseModel):
    dataset_spec: Dict[str, Any] = Field(
        description="Dataset spec object returned by build_dataset_spec.",
    )
    dataset_profile: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional dataset inspection payload returned by inspect_dataset.",
    )
