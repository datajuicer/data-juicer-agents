# -*- coding: utf-8 -*-
"""Registry for process tool specs."""

from __future__ import annotations

from typing import List

from data_juicer_agents.core.tool import ToolSpec

from .execute_python_code.tool import EXECUTE_PYTHON_CODE
from .execute_shell_command.tool import EXECUTE_SHELL_COMMAND

TOOL_SPECS: List[ToolSpec] = [EXECUTE_SHELL_COMMAND, EXECUTE_PYTHON_CODE]

__all__ = ["EXECUTE_PYTHON_CODE", "EXECUTE_SHELL_COMMAND", "TOOL_SPECS"]
