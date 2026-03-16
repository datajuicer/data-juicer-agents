# -*- coding: utf-8 -*-
"""Tool spec for plan_save."""

from __future__ import annotations

from pydantic import BaseModel

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import PlanSaveInput
from .logic import save_plan_file


class GenericOutput(BaseModel):
    ok: bool = True


def _plan_save(_ctx: ToolContext, args: PlanSaveInput) -> ToolResult:
    result = save_plan_file(
        plan_payload=args.plan_payload,
        output_path=args.output_path,
        overwrite=args.overwrite,
    )
    if result.get("ok"):
        return ToolResult.success(summary=str(result.get("message", "plan saved")), data=result)
    return ToolResult.failure(
        summary=str(result.get("message", "plan save failed")),
        error_type=str(result.get("error_type", "plan_save_failed")),
        error_message=str(result.get("error_message", "")).strip(),
        data=result,
    )


PLAN_SAVE = ToolSpec(
    name="plan_save",
    description=(
        "Persist an explicit plan_payload object to disk. Pass the full plan returned by assemble_plan "
        "and an explicit output_path."
    ),
    input_model=PlanSaveInput,
    output_model=GenericOutput,
    executor=_plan_save,
    tags=("plan",),
    effects="write",
    confirmation="none",
)


__all__ = ["PLAN_SAVE"]
