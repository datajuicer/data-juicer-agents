# -*- coding: utf-8 -*-
"""Registry for file tool specs."""

from __future__ import annotations

from typing import List

from data_juicer_agents.core.tool import ToolSpec

from .insert_text_file.tool import INSERT_TEXT_FILE
from .view_text_file.tool import VIEW_TEXT_FILE
from .write_text_file.tool import WRITE_TEXT_FILE

TOOL_SPECS: List[ToolSpec] = [VIEW_TEXT_FILE, WRITE_TEXT_FILE, INSERT_TEXT_FILE]

__all__ = ["INSERT_TEXT_FILE", "TOOL_SPECS", "VIEW_TEXT_FILE", "WRITE_TEXT_FILE"]
