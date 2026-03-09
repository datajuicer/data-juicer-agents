# -*- coding: utf-8 -*-
"""Shared logging helpers for AgentScope integration."""

from __future__ import annotations

import logging


THINKING_BLOCK_WARNING = "Unsupported block type thinking in the message, skipped."


class IgnoreThinkingBlockWarningFilter(logging.Filter):
    """Filter only the known formatter warning for thinking blocks."""

    def filter(self, record: logging.LogRecord) -> bool:
        return THINKING_BLOCK_WARNING not in record.getMessage()


def install_thinking_warning_filter(logger_name: str = "as") -> None:
    """Install the filter once on the target logger."""
    logger = logging.getLogger(logger_name)
    for item in logger.filters:
        if isinstance(item, IgnoreThinkingBlockWarningFilter):
            return
    logger.addFilter(IgnoreThinkingBlockWarningFilter())
