# -*- coding: utf-8 -*-
"""Tool spec for insert_text_file."""

from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import GenericOutput, InsertTextFileInput
from .logic import insert_text_file


def _insert_text_file(_ctx: ToolContext, args: InsertTextFileInput) -> ToolResult:
    payload = insert_text_file(file_path=args.file_path, content=args.content, line_number=args.line_number)
    if payload.get("ok"):
        return ToolResult.success(summary=str(payload.get("message", "inserted content")), data=payload)
    return ToolResult.failure(
        summary=str(payload.get("message", "insert_text_file failed")),
        error_type=str(payload.get("error_type", "insert_text_file_failed")),
        data=payload,
    )


INSERT_TEXT_FILE = ToolSpec(
    name="insert_text_file",
    description="Insert content into a text file at a specific line.",
    input_model=InsertTextFileInput,
    output_model=GenericOutput,
    executor=_insert_text_file,
    tags=("file", "write"),
    effects="write",
    confirmation="recommended",
)


__all__ = ["INSERT_TEXT_FILE"]
