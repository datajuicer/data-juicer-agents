# -*- coding: utf-8 -*-
"""Input models for insert_text_file."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InsertTextFileInput(BaseModel):
    file_path: str = Field(description="Target text file path.")
    content: str = Field(default="", description="Content to insert.")
    line_number: int = Field(ge=1, description="1-based insertion line number.")


class GenericOutput(BaseModel):
    ok: bool = True
