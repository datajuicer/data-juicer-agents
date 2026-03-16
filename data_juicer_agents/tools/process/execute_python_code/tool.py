# -*- coding: utf-8 -*-
"""Tool spec for execute_python_code."""

from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ExecutePythonCodeInput, GenericOutput
from .logic import execute_python_code


def _execute_python_code(_ctx: ToolContext, args: ExecutePythonCodeInput) -> ToolResult:
    payload = execute_python_code(code=args.code, timeout=args.timeout)
    if payload.get("ok"):
        return ToolResult.success(summary=str(payload.get("message", "python finished")), data=payload)
    return ToolResult.failure(
        summary=str(payload.get("message", "python execution failed")),
        error_type=str(payload.get("error_type", "execution_failed")),
        data=payload,
    )


EXECUTE_PYTHON_CODE = ToolSpec(
    name="execute_python_code",
    description="Execute a Python snippet and capture stdout/stderr.",
    input_model=ExecutePythonCodeInput,
    output_model=GenericOutput,
    executor=_execute_python_code,
    tags=("process", "execute"),
    effects="execute",
    confirmation="recommended",
)


__all__ = ["EXECUTE_PYTHON_CODE"]
