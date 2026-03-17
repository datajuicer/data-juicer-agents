# -*- coding: utf-8 -*-
"""Input models for retrieve_operators."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetrieveOperatorsInput(BaseModel):
    intent: str = Field(description="Natural-language retrieval intent.")
    top_k: int = Field(default=10, ge=1, description="Maximum number of operator candidates to return.")
    mode: str = Field(default="auto", description="Retrieval mode: auto, llm, or vector.")
    dataset_path: str = Field(default="", description="Optional dataset path used as explicit retrieval context.")


class GenericOutput(BaseModel):
    ok: bool = True
