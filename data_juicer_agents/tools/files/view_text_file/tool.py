# -*- coding: utf-8 -*-
"""Tool spec for view_text_file."""

from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import GenericOutput, ViewTextFileInput
from .logic import view_text_file


def _view_text_file(_ctx: ToolContext, args: ViewTextFileInput) -> ToolResult:
    payload = view_text_file(file_path=args.file_path, ranges=args.ranges)
    if payload.get("ok"):
        return ToolResult.success(summary=str(payload.get("message", "loaded file")), data=payload)
    return ToolResult.failure(
        summary=str(payload.get("message", "view_text_file failed")),
        error_type=str(payload.get("error_type", "view_text_file_failed")),
        data=payload,
    )


VIEW_TEXT_FILE = ToolSpec(
    name="view_text_file",
    description="Read a text file with optional line ranges.",
    input_model=ViewTextFileInput,
    output_model=GenericOutput,
    executor=_view_text_file,
    tags=("file", "read"),
    effects="read",
    confirmation="none",
)


__all__ = ["VIEW_TEXT_FILE"]
