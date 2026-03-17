# -*- coding: utf-8 -*-
"""Input models for inspect_dataset."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InspectDatasetInput(BaseModel):
    dataset_path: str = Field(description="Dataset file path to inspect.")
    sample_size: int = Field(default=20, ge=1, description="Number of samples to inspect.")


class GenericOutput(BaseModel):
    ok: bool = True
