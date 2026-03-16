# -*- coding: utf-8 -*-
"""Input models for apply_recipe."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ApplyRecipeInput(BaseModel):
    plan_path: str = Field(description="Plan YAML path to execute.")
    dry_run: bool = Field(default=False, description="If true, do not execute dj-process.")
    timeout: int = Field(default=300, ge=1, description="Execution timeout in seconds.")
    confirm: bool = Field(default=False, description="Explicit confirmation required before execution.")


class GenericOutput(BaseModel):
    ok: bool = True
