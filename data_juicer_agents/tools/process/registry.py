# -*- coding: utf-8 -*-
"""Registry for process tool specs."""

from __future__ import annotations

from typing import List

from data_juicer_agents.core.tool import ToolSpec

from .execute_bash.tool import EXECUTE_BASH
from .execute_python_code.tool import EXECUTE_PYTHON_CODE

TOOL_SPECS: List[ToolSpec] = [EXECUTE_BASH, EXECUTE_PYTHON_CODE]

__all__ = ["EXECUTE_BASH", "EXECUTE_PYTHON_CODE", "TOOL_SPECS"]
