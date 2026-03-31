# -*- coding: utf-8 -*-
"""Input models for retrieve_operators."""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class RetrieveOperatorsInput(BaseModel):
    intent: str = Field(
        description=(
            "Retrieval query. For natural-language modes (auto, llm, vector, bm25), "
            "provide a plain-text description of the desired operators. "
            "For regex mode, provide a regular expression pattern to match operator names."
        )
    )
    top_k: int = Field(default=10, ge=1, description="Maximum number of operator candidates to return.")
    mode: Literal["auto", "llm", "vector", "bm25", "regex"] = Field(
        default="auto",
        description=(
            "Retrieval mode. "
            "'auto': tries llm → vector → bm25 with automatic fallback. "
            "'llm': semantic ranking via LLM (most accurate, requires API key, slower). "
            "'vector': FAISS vector similarity (requires API key, fast after index built). "
            "'bm25': BM25 keyword matching (no API key needed, fast). "
            "'regex': regex pattern matching on operator names (no API key needed, fastest)."
        ),
    )
    op_type: str = Field(
        default="",
        description=(
            "Optional operator type filter (e.g. 'filter', 'mapper', 'deduplicator', "
            "'selector', 'grouper', 'aggregator', 'pipeline'). When provided, only operators of "
            "the specified type are considered during retrieval."
        ),
    )
    tags: List[str] = Field(
        default_factory=list,
        description=(
            "Modality/resource tags to filter operators "
            "(e.g. 'text', 'image', 'multimodal', 'audio', 'video', 'cpu', 'gpu', 'api'). "
            "Only operators whose tag set contains ALL of the specified tags are returned (match-all semantics)."
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