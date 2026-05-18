# -*- coding: utf-8 -*-
"""Tool spec for execute_bash — SmartBash harness."""

from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ExecuteBashInput, GenericOutput
from .logic import execute_bash


def _execute_bash(_ctx: ToolContext, args: ExecuteBashInput) -> ToolResult:
    payload = execute_bash(
        command=args.command,
        timeout=args.timeout,
        working_dir=args.working_dir,
    )
    if payload.get("ok"):
        return ToolResult.success(
            summary=str(payload.get("summary", "command finished")),
            data=payload,
        )
    diag = str(payload.get("diagnosis", ""))
    suggestion = str(payload.get("suggestion", ""))
    summary = str(payload.get("summary", "command failed"))
    if diag:
        summary += f". {diag}"
    result = ToolResult.failure(
        summary=summary,
        error_type=str(payload.get("error_type", "command_failed")),
        data=payload,
    )
    if suggestion:
        result.next_actions = [suggestion]
    return result


EXECUTE_BASH = ToolSpec(
    name="execute_bash",
    description=(
        "Execute a bash command with smart output parsing. "
        "Automatically detects command type (grep, find, tail, head, cat, wc, ls) "
        "and returns structured results with match counts, file lists, etc. "
        "On failure, provides diagnosis and fix suggestions. "
        "Use this for any shell operation: searching files, listing directories, "
        "reading logs, counting lines, etc."
    ),
    input_model=ExecuteBashInput,
    output_model=GenericOutput,
    executor=_execute_bash,
    tags=("bash", "execute"),
    effects="execute",
    confirmation="recommended",
)

__all__ = ["EXECUTE_BASH"]
