# -*- coding: utf-8 -*-
"""Input models for write_text_file."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WriteTextFileInput(BaseModel):
    file_path: str = Field(description="Target text file path.")
    content: str = Field(default="", description="Content to write.")
    ranges: Any = Field(default=None, description="Optional line range to replace.")


class GenericOutput(BaseModel):
    ok: bool = True
