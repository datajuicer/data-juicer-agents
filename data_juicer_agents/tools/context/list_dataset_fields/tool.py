# -*- coding: utf-8 -*-
"""Tool spec for list_dataset_fields."""

from __future__ import annotations

from pydantic import BaseModel

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ListDatasetFieldsInput
from .logic import list_dataset_fields


class ListDatasetFieldsOutput(BaseModel):
    ok: bool = True
    message: str = ""
    fields: dict = {}
    total_count: int = 0
    filter_applied: str | None = None


def _list_dataset_fields(_ctx: ToolContext, args: ListDatasetFieldsInput) -> ToolResult:
    result = list_dataset_fields(
        filter_prefix=args.filter_prefix,
        include_descriptions=args.include_descriptions,
    )

    if result.get("ok"):
        return ToolResult.success(
            summary=f"Listed {result['total_count']} dataset configuration fields",
            data=result,
        )

    return ToolResult.failure(
        summary=result.get("message", "Failed to list dataset fields"),
        error_type="dataset_fields_list_failed",
        data=result,
    )


LIST_DATASET_FIELDS = ToolSpec(
    name="list_dataset_fields",
    description=(
        "List all dataset-related configuration fields recognized by Data-Juicer. "
        "Returns field names, types, default values, and descriptions. "
        "Call this BEFORE build_dataset_spec when you need advanced options "
        "such as export_type, export_shard_size, export_in_parallel, "
        "load_dataset_kwargs, suffixes, or modality special tokens "
        "(image_special_token, audio_special_token, video_special_token, eoc_special_token). "
        "Do NOT confuse these advanced dataset fields with dataset_source itself: "
        "dataset_source.path/config/generated selects the input source, while the fields "
        "returned here tweak the dataset spec around that source."
    ),
    input_model=ListDatasetFieldsInput,
    output_model=ListDatasetFieldsOutput,
    executor=_list_dataset_fields,
    tags=("context", "discovery", "dataset"),
    effects="read",
    confirmation="none",
)

__all__ = ["LIST_DATASET_FIELDS"]
