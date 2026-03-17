# -*- coding: utf-8 -*-
"""Tool spec for plan_validate."""

from __future__ import annotations

from pydantic import BaseModel

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import PlanValidateInput
from .logic import plan_validate


class GenericOutput(BaseModel):
    ok: bool = True


def _plan_validate(_ctx: ToolContext, args: PlanValidateInput) -> ToolResult:
    result = plan_validate(plan_payload=args.plan_payload)
    if result.get("ok"):
        return ToolResult.success(summary=str(result.get("message", "plan is valid")), data=result)
    return ToolResult.failure(
        summary=str(result.get("message", "plan validation failed")),
        error_type=str(result.get("error_type", "plan_invalid")),
        error_message=str(result.get("error_message", "")).strip(),
        data=result,
    )


PLAN_VALIDATE = ToolSpec(
    name="plan_validate",
    description="Validate an explicit plan_payload object returned by assemble_plan or loaded from disk.",
    input_model=PlanValidateInput,
    output_model=GenericOutput,
    executor=_plan_validate,
    tags=("plan",),
    effects="read",
    confirmation="none",
)


__all__ = ["PLAN_VALIDATE"]
