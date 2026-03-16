# -*- coding: utf-8 -*-
"""Tool spec for validate_system_spec."""

from __future__ import annotations

from pydantic import BaseModel

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ValidateSystemSpecInput
from .logic import validate_system_spec


class GenericOutput(BaseModel):
    ok: bool = True


def _validate_system_spec(_ctx: ToolContext, args: ValidateSystemSpecInput) -> ToolResult:
    payload = validate_system_spec(system_spec=args.system_spec)
    if payload["ok"]:
        return ToolResult.success(summary=payload["message"], data=payload)
    return ToolResult.failure(summary=payload["message"], error_type="system_spec_invalid", data=payload)


VALIDATE_SYSTEM_SPEC = ToolSpec(
    name="validate_system_spec",
    description="Validate an explicit system spec and report deferred warnings.",
    input_model=ValidateSystemSpecInput,
    output_model=GenericOutput,
    executor=_validate_system_spec,
    tags=("plan",),
    effects="read",
    confirmation="none",
)


__all__ = ["VALIDATE_SYSTEM_SPEC"]
