# -*- coding: utf-8 -*-
"""Input models for retrieve_operators_api."""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class RetrieveOperatorsAPIInput(BaseModel):
    intent: str = Field(
        description=(
            "Retrieval query for API-backed semantic retrieval. "
            "Provide a plain-text description of the desired operators."
        )
    )
    top_k: int = Field(default=10, ge=1, description="Maximum number of operator candidates to return.")
    mode: Literal["auto", "llm", "vector"] = Field(
        default="auto",
        description=(
            "API-backed retrieval mode. "
            "'auto': tries llm -> vector. "
            "'llm': semantic ranking via LLM. "
            "'vector': FAISS vector similarity."
        ),
    )
    op_type: str = Field(
        default="",
        description=(
            "Optional operator type filter (e.g. 'filter', 'mapper', 'deduplicator', "
            "'selector', 'grouper', 'aggregator', 'pipeline')."
        ),
    )
    tags: List[str] = Field(
        default_factory=list,
        description=(
            "Modality/resource tags to filter operators "
            "(e.g. 'text', 'image', 'multimodal', 'audio', 'video', 'cpu', 'gpu', 'api'). "
            "Only operators whose tag set contains ALL of the specified tags are returned."
        ),
    )
class GenericOutput(BaseModel):
    ok: bool = True
