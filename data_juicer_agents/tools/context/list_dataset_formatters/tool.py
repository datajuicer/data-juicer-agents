# -*- coding: utf-8 -*-
"""Tool spec for list_dataset_formatters."""

from __future__ import annotations

from pydantic import BaseModel

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ListDatasetFormattersInput
from .logic import list_dataset_formatters


class ListDatasetFormattersOutput(BaseModel):
    ok: bool = True
    message: str = ""
    formatters: list = []
    total_count: int = 0
    include_ray: bool = True
    usage_hint: str = ""


def _list_dataset_formatters(
    _ctx: ToolContext, args: ListDatasetFormattersInput
) -> ToolResult:
    result = list_dataset_formatters(include_ray=args.include_ray)

    if result.get("ok"):
        return ToolResult.success(
            summary=f"Found {result['total_count']} dataset formatters",
            data=result,
        )

    return ToolResult.failure(
        summary=result.get("message", "Failed to list dataset formatters"),
        error_type="dataset_formatters_list_failed",
        data=result,
    )


LIST_DATASET_FORMATTERS = ToolSpec(
    name="list_dataset_formatters",
    description=(
        "Discover which dataset formatters (dynamic data generators) are available "
        "in the current Data-Juicer installation. Returns formatter names, descriptions, "
        "and their configuration parameters. "
        "Use this BEFORE build_dataset_spec when you need to configure the "
        "generated_dataset_config field for dynamic dataset generation "
        "(e.g., EmptyFormatter for creating empty datasets, or file-based formatters "
        "like JsonFormatter, CsvFormatter, TextFormatter, etc.)."
    ),
    input_model=ListDatasetFormattersInput,
    output_model=ListDatasetFormattersOutput,
    executor=_list_dataset_formatters,
    tags=("context", "discovery", "dataset"),
    effects="read",
    confirmation="none",
)

__all__ = ["LIST_DATASET_FORMATTERS"]
