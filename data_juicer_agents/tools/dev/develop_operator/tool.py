# -*- coding: utf-8 -*-
"""Tool spec for develop_operator."""

from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec
from data_juicer_agents.utils.runtime_helpers import to_bool

from .input import DevelopOperatorInput, GenericOutput
from .logic import DevUseCase


def _develop_operator(_ctx: ToolContext, args: DevelopOperatorInput) -> ToolResult:
    result = DevUseCase.execute(
        intent=args.intent.strip(),
        operator_name=args.operator_name.strip(),
        output_dir=args.output_dir.strip(),
        operator_type=(args.operator_type.strip() or None),
        from_retrieve=(args.from_retrieve.strip() or None),
        smoke_check=to_bool(args.smoke_check, False),
    )
    if not result.get("ok"):
        return ToolResult.failure(
            summary=str(result.get("message", "dev scaffold generation failed")),
            error_type=str(result.get("error_type", "dev_failed")),
            data={
                "ok": False,
                "error_type": str(result.get("error_type", "dev_failed")),
                "requires": list(result.get("requires", [])),
                "message": str(result.get("message", "dev scaffold generation failed")),
            },
        )

    payload = {
        "ok": bool(result.get("ok")),
        "action": "dev",
        "operator_name": str(result.get("operator_name", "")),
        "operator_type": str(result.get("operator_type", "")),
        "class_name": str(result.get("class_name", "")),
        "output_dir": str(result.get("output_dir", "")),
        "generated_files": list(result.get("generated_files", [])),
        "summary_path": str(result.get("summary_path", "")),
        "notes": list(result.get("notes", [])),
    }
    if result.get("smoke_check") is not None:
        payload["smoke_check"] = result.get("smoke_check")
    return ToolResult.success(summary="operator scaffold generated", data=payload)


DEVELOP_OPERATOR = ToolSpec(
    name="develop_operator",
    description="Generate a custom Data-Juicer operator scaffold from explicit intent.",
    input_model=DevelopOperatorInput,
    output_model=GenericOutput,
    executor=_develop_operator,
    tags=("dev", "operator"),
    effects="write",
    confirmation="recommended",
)


__all__ = ["DEVELOP_OPERATOR"]
