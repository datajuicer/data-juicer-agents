# -*- coding: utf-8 -*-
"""Registry for retrieve tool specs."""

from __future__ import annotations

from typing import List

from data_juicer_agents.core.tool import ToolSpec

from .retrieve_operators.tool import RETRIEVE_OPERATORS

TOOL_SPECS: List[ToolSpec] = [RETRIEVE_OPERATORS]

__all__ = ["RETRIEVE_OPERATORS", "TOOL_SPECS"]
