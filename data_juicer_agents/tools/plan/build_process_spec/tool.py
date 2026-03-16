# -*- coding: utf-8 -*-
"""Tool spec for build_process_spec."""

from __future__ import annotations

from pydantic import BaseModel

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import BuildProcessSpecInput
from .logic import build_process_spec


class GenericOutput(BaseModel):
    ok: bool = True


def _build_process_spec(_ctx: ToolContext, args: BuildProcessSpecInput) -> ToolResult:
    result = build_process_spec(operators=[item.model_dump() for item in args.operators])
    if result.get("ok"):
        return ToolResult.success(summary=str(result.get("message", "process spec built")), data=result)
    return ToolResult.failure(
        summary=str(result.get("message", "process spec build failed")),
        error_type=str(result.get("error_type", "build_process_spec_failed")),
        error_message=str(result.get("error_message", "")).strip(),
        data=result,
    )


BUILD_PROCESS_SPEC = ToolSpec(
    name="build_process_spec",
    description=(
        "Build a deterministic process spec from an explicit operators array. Pass canonical operator "
        "names from retrieve_operators and fill suitable params for each operator."
    ),
    input_model=BuildProcessSpecInput,
    output_model=GenericOutput,
    executor=_build_process_spec,
    tags=("plan",),
    effects="write",
    confirmation="none",
)


__all__ = ["BUILD_PROCESS_SPEC"]
