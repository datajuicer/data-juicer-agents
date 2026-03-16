# -*- coding: utf-8 -*-
"""Tool spec for assemble_plan."""

from __future__ import annotations

from pydantic import BaseModel

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import AssemblePlanInput
from .logic import assemble_plan


class GenericOutput(BaseModel):
    ok: bool = True


def _assemble_plan(_ctx: ToolContext, args: AssemblePlanInput) -> ToolResult:
    result = assemble_plan(
        user_intent=args.intent,
        dataset_spec=args.dataset_spec,
        process_spec=args.process_spec,
        system_spec=args.system_spec,
        approval_required=args.approval_required,
    )
    if result.get("ok"):
        return ToolResult.success(summary="plan draft assembled", data=result)
    return ToolResult.failure(
        summary=str(result.get("message", "assemble_plan failed")),
        error_type=str(result.get("error_type", "assemble_plan_failed")),
        error_message=str(result.get("error_message", "")).strip(),
        data=result,
    )


ASSEMBLE_PLAN = ToolSpec(
    name="assemble_plan",
    description=(
        "Assemble a plan from explicit intent, dataset_spec, process_spec, and system_spec objects. "
        "Pass the full spec objects returned by the previous staged planning tools."
    ),
    input_model=AssemblePlanInput,
    output_model=GenericOutput,
    executor=_assemble_plan,
    tags=("plan",),
    effects="write",
    confirmation="none",
)


__all__ = ["ASSEMBLE_PLAN"]
