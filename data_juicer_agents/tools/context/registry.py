# -*- coding: utf-8 -*-
"""Registry for context tool specs."""

from __future__ import annotations

from typing import List

from data_juicer_agents.core.tool import ToolSpec

from .inspect_dataset.tool import INSPECT_DATASET

TOOL_SPECS: List[ToolSpec] = [INSPECT_DATASET]

__all__ = ["INSPECT_DATASET", "TOOL_SPECS"]
