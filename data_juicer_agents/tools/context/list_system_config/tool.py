# -*- coding: utf-8 -*-
"""Tool spec for list_system_config."""

from __future__ import annotations

from pydantic import BaseModel

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ListSystemConfigInput
from .logic import list_system_config

class ListSystemConfigOutput(BaseModel):
    ok: bool = True
    message: str = ""
    config: dict = {}
    total_count: int = 0
    filter_applied: str | None = None

def _list_system_config(_ctx: ToolContext, args: ListSystemConfigInput) -> ToolResult:
    result = list_system_config(
        filter_prefix=args.filter_prefix,
        include_descriptions=args.include_descriptions
    )
    
    if result.get("ok"):
        return ToolResult.success(
            summary=f"Listed {result['total_count']} system configuration parameters",
            data=result
        )
    
    return ToolResult.failure(
        summary=result.get("message", "Failed to list system config"),
        error_type="system_config_list_failed",
        data=result
    )

LIST_SYSTEM_CONFIG = ToolSpec(
    name="list_system_config",
    description=(
        "List the complete system configuration from Data-Juicer. "
        "This tool returns all available system parameters, their types, default values, and descriptions. "
        "Use this BEFORE build_system_spec to discover what configuration options are available. "
        "You can optionally filter by prefix (e.g., 'open_' for tracing options) "
        "or get descriptions for all parameters."
    ),
    input_model=ListSystemConfigInput,
    output_model=ListSystemConfigOutput,
    executor=_list_system_config,
    tags=("context", "discovery", "configuration"),
    effects="read",
    confirmation="none",
)

__all__ = ["LIST_SYSTEM_CONFIG"]
