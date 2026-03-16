# -*- coding: utf-8 -*-
"""Tool spec for validate_process_spec."""

from __future__ import annotations

from pydantic import BaseModel

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ValidateProcessSpecInput
from .logic import validate_process_spec


class GenericOutput(BaseModel):
    ok: bool = True


def _validate_process_spec(_ctx: ToolContext, args: ValidateProcessSpecInput) -> ToolResult:
    payload = validate_process_spec(process_spec=args.process_spec)
    if payload["ok"]:
        return ToolResult.success(summary=payload["message"], data=payload)
    return ToolResult.failure(summary=payload["message"], error_type="process_spec_invalid", data=payload)


VALIDATE_PROCESS_SPEC = ToolSpec(
    name="validate_process_spec",
    description="Validate an explicit process spec structurally and report deferred warnings.",
    input_model=ValidateProcessSpecInput,
    output_model=GenericOutput,
    executor=_validate_process_spec,
    tags=("plan",),
    effects="read",
    confirmation="none",
)


__all__ = ["VALIDATE_PROCESS_SPEC"]
