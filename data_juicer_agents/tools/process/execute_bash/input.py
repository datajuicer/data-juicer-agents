# -*- coding: utf-8 -*-
"""Input model for execute_bash."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExecuteBashInput(BaseModel):
    command: str = Field(
        description=(
            "Shell command to execute. Supports any standard Unix command "
            "(grep, find, tail, head, cat, wc, ls, etc.). "
            "The output is automatically parsed based on the command type "
            "(grep returns match count + lines, find returns file list, etc.) "
            "and truncated to keep the context window small."
        )
    )
    timeout: int = Field(
        default=120,
        ge=1,
        description="Maximum execution time in seconds.",
    )


class GenericOutput(BaseModel):
    ok: bool = True
