# -*- coding: utf-8 -*-
"""Tool spec for execute_shell_command."""

from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ExecuteShellCommandInput, GenericOutput
from .logic import execute_shell_command


def _execute_shell_command(_ctx: ToolContext, args: ExecuteShellCommandInput) -> ToolResult:
    payload = execute_shell_command(command=args.command, timeout=args.timeout)
    if payload.get("ok"):
        return ToolResult.success(summary=str(payload.get("message", "command finished")), data=payload)
    return ToolResult.failure(
        summary=str(payload.get("message", "command failed")),
        error_type=str(payload.get("error_type", "command_failed")),
        data=payload,
    )


EXECUTE_SHELL_COMMAND = ToolSpec(
    name="execute_shell_command",
    description="Execute a shell command and capture stdout/stderr.",
    input_model=ExecuteShellCommandInput,
    output_model=GenericOutput,
    executor=_execute_shell_command,
    tags=("process", "execute"),
    effects="execute",
    confirmation="recommended",
)


__all__ = ["EXECUTE_SHELL_COMMAND"]
