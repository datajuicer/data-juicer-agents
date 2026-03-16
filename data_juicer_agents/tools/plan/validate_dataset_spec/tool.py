# -*- coding: utf-8 -*-
"""Tool spec for validate_dataset_spec."""

from __future__ import annotations

from pydantic import BaseModel

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ValidateDatasetSpecInput
from .logic import validate_dataset_spec


class GenericOutput(BaseModel):
    ok: bool = True


def _validate_dataset_spec(_ctx: ToolContext, args: ValidateDatasetSpecInput) -> ToolResult:
    payload = validate_dataset_spec(dataset_spec=args.dataset_spec, dataset_profile=args.dataset_profile)
    if payload["ok"]:
        return ToolResult.success(summary=payload["message"], data=payload)
    return ToolResult.failure(summary=payload["message"], error_type="dataset_spec_invalid", data=payload)


VALIDATE_DATASET_SPEC = ToolSpec(
    name="validate_dataset_spec",
    description="Validate an explicit dataset spec and optional dataset_profile payload.",
    input_model=ValidateDatasetSpecInput,
    output_model=GenericOutput,
    executor=_validate_dataset_spec,
    tags=("plan",),
    effects="read",
    confirmation="none",
)


__all__ = ["VALIDATE_DATASET_SPEC"]
