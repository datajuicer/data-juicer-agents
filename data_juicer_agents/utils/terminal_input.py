# -*- coding: utf-8 -*-
"""Shared terminal line input for plain/TUI session entrypoints."""

from __future__ import annotations

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory


class TerminalLineReader:
    """Unicode-safe line reader backed by prompt_toolkit."""

    def __init__(self) -> None:
        self._session = PromptSession(
            history=InMemoryHistory(),
            complete_while_typing=False,
        )

    def read_line(self, prompt: str) -> str:
        return self._session.prompt(prompt)
