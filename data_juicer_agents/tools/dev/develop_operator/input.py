# -*- coding: utf-8 -*-
"""Input models for develop_operator."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DevelopOperatorInput(BaseModel):
    intent: str = Field(description="Requirement that current operators cannot satisfy.")
    operator_name: str = Field(default="", description="Target operator name.")
    output_dir: str = Field(default="", description="Directory to write generated operator scaffold.")
    operator_type: str = Field(default="", description="Optional operator type such as mapper or filter.")
    from_retrieve: str = Field(default="", description="Optional retrieval payload path used as reference.")
    smoke_check: bool = Field(default=False, description="Run smoke validation after scaffold generation.")


class GenericOutput(BaseModel):
    ok: bool = True
