# -*- coding: utf-8 -*-
"""Input models for build_system_spec."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class BuildSystemSpecInput(BaseModel):
    custom_operator_paths: List[str] = Field(default_factory=list, description="Optional custom operator paths.")
