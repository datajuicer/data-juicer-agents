# -*- coding: utf-8 -*-
"""Tool spec for build_system_spec."""

from __future__ import annotations

from pydantic import BaseModel

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import BuildSystemSpecInput
from .logic import build_system_spec

class GenericOutput(BaseModel):
    ok: bool = True

def _build_system_spec(_ctx: ToolContext, args: BuildSystemSpecInput) -> ToolResult:
    # Get all extra fields (beyond the core ones)
    extra_config = {
        k: v for k, v in args.model_dump().items()
        if k not in ('np', 'executor_type', 'custom_operator_paths')
        and v is not None
    }
    
    result = build_system_spec(
        custom_operator_paths=args.custom_operator_paths,
        np=args.np,
        executor_type=args.executor_type,
        extra_config=extra_config if extra_config else None
    )
    if result.get("ok"):
        return ToolResult.success(summary=str(result.get("message", "system spec built")), data=result)
    return ToolResult.failure(
        summary=str(result.get("message", "system spec build failed")),
        error_type=str(result.get("error_type", "build_system_spec_failed")),
        error_message=str(result.get("error_message", "")).strip(),
        data=result,
    )

BUILD_SYSTEM_SPEC = ToolSpec(
    name="build_system_spec",
    description=(
        "Build a system spec with Data-Juicer configuration. "
        "Core parameters: np, executor_type, custom_operator_paths. "
        "Advanced parameters (open_tracer, use_cache, checkpoint, etc.) can be passed directly. "
        "Use list_system_config to discover all available system configuration options."
    ),
    input_model=BuildSystemSpecInput,
    output_model=GenericOutput,
    executor=_build_system_spec,
    tags=("plan",),
    effects="write",
    confirmation="none",
)

__all__ = ["BUILD_SYSTEM_SPEC"]


BUILD_SYSTEM_SPEC = ToolSpec(
    name="build_system_spec",
    description=(
        "Build a system spec with Data-Juicer configuration. "
        "Specify core parameters (np, executor_type, custom_operator_paths) directly, "
        "or use extra_config for advanced options. "
        "Use list_system_config to discover all available system configuration options."
    ),
    input_model=BuildSystemSpecInput,
    output_model=GenericOutput,
    executor=_build_system_spec,
    tags=("plan",),
    effects="write",
    confirmation="none",
)


__all__ = ["BUILD_SYSTEM_SPEC"]
