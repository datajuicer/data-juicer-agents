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
    mode: Literal["auto", "llm"] = Field(
        default="auto",
        description=(
            "API-backed retrieval mode. "
            "'auto': uses llm. "
            "'llm': semantic ranking via LLM. "
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
    dataset_path: str = Field(
        default="",
        description=(
            "Optional dataset file path. When provided, the dataset modality is probed "
            "via inspect_dataset_schema and the inferred tags are merged with any explicit tags."
        ),
    )


class GenericOutput(BaseModel):
    ok: bool = True
