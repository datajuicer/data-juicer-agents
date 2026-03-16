# -*- coding: utf-8 -*-
"""Input models for validate_system_spec."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class ValidateSystemSpecInput(BaseModel):
    system_spec: Dict[str, Any] = Field(
        description="System spec object returned by build_system_spec.",
    )
