# -*- coding: utf-8 -*-
"""Input models for view_text_file."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ViewTextFileInput(BaseModel):
    file_path: str = Field(description="Target text file path.")
    ranges: Any = Field(default=None, description="Optional line range as [start, end].")


class GenericOutput(BaseModel):
    ok: bool = True
