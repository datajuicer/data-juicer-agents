# -*- coding: utf-8 -*-
"""Input models for validate_process_spec."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class ValidateProcessSpecInput(BaseModel):
    process_spec: Dict[str, Any] = Field(
        description="Process spec object returned by build_process_spec.",
    )
