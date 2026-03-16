# -*- coding: utf-8 -*-
"""Registry for dev tool specs."""

from __future__ import annotations

from typing import List

from data_juicer_agents.core.tool import ToolSpec

from .develop_operator.tool import DEVELOP_OPERATOR

TOOL_SPECS: List[ToolSpec] = [DEVELOP_OPERATOR]

__all__ = ["DEVELOP_OPERATOR", "TOOL_SPECS"]
