# -*- coding: utf-8 -*-
"""Input models for execute_python_code."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExecutePythonCodeInput(BaseModel):
    code: str = Field(description="Python code snippet to execute.")
    timeout: int = Field(default=120, ge=1, description="Timeout in seconds.")


class GenericOutput(BaseModel):
    ok: bool = True
