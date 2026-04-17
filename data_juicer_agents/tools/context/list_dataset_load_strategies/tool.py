# -*- coding: utf-8 -*-
"""Tool spec for list_dataset_load_strategies."""

from __future__ import annotations

from pydantic import BaseModel

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ListDatasetLoadStrategiesInput
from .logic import list_dataset_load_strategies


class ListDatasetLoadStrategiesOutput(BaseModel):
    ok: bool = True
    message: str = ""
    executor_type_filter: str = "default"
    strategies: list = []
    total_count: int = 0
    usage_hint: str = ""


def _list_dataset_load_strategies(
    _ctx: ToolContext, args: ListDatasetLoadStrategiesInput
) -> ToolResult:
    result = list_dataset_load_strategies(executor_type=args.executor_type)

    if result.get("ok"):
        return ToolResult.success(
            summary=(
                f"Found {result['total_count']} implemented dataset load strategies "
                f"for executor_type='{args.executor_type}'"
            ),
            data=result,
        )

    return ToolResult.failure(
        summary=result.get("message", "Failed to list dataset load strategies"),
        error_type="dataset_load_strategies_list_failed",
        data=result,
    )


LIST_DATASET_LOAD_STRATEGIES = ToolSpec(
    name="list_dataset_load_strategies",
    description=(
        "Discover which dataset loading strategies are truly implemented in the current "
        "Data-Juicer installation. Returns available type/source combinations with their "
        "required and optional config fields. "
        "Use this BEFORE build_dataset_spec when you need to configure non-trivial dataset "
        "sources (e.g., remote S3, mixed-weight local files). "
        "For simple single local files, use dataset_source.path directly in build_dataset_spec."
    ),
    input_model=ListDatasetLoadStrategiesInput,
    output_model=ListDatasetLoadStrategiesOutput,
    executor=_list_dataset_load_strategies,
    tags=("context", "discovery", "dataset"),
    effects="read",
    confirmation="none",
)

__all__ = ["LIST_DATASET_LOAD_STRATEGIES"]
