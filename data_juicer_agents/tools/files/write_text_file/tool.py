# -*- coding: utf-8 -*-
"""Tool spec for write_text_file."""

from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import GenericOutput, WriteTextFileInput
from .logic import write_text_file


def _write_text_file(_ctx: ToolContext, args: WriteTextFileInput) -> ToolResult:
    payload = write_text_file(file_path=args.file_path, content=args.content, ranges=args.ranges)
    if payload.get("ok"):
        return ToolResult.success(summary=str(payload.get("message", "wrote file")), data=payload)
    return ToolResult.failure(
        summary=str(payload.get("message", "write_text_file failed")),
        error_type=str(payload.get("error_type", "write_text_file_failed")),
        data=payload,
    )


WRITE_TEXT_FILE = ToolSpec(
    name="write_text_file",
    description="Write or replace a text file, or replace a line range in a text file.",
    input_model=WriteTextFileInput,
    output_model=GenericOutput,
    executor=_write_text_file,
    tags=("file", "write"),
    effects="write",
    confirmation="recommended",
)


__all__ = ["WRITE_TEXT_FILE"]
