# -*- coding: utf-8 -*-
"""Registry for context tool specs."""

from __future__ import annotations

from typing import List

from data_juicer_agents.core.tool import ToolSpec

from .inspect_dataset.tool import INSPECT_DATASET
from .list_dataset_fields.tool import LIST_DATASET_FIELDS
from .list_dataset_formatters.tool import LIST_DATASET_FORMATTERS
from .list_dataset_load_strategies.tool import LIST_DATASET_LOAD_STRATEGIES
from .list_system_config.tool import LIST_SYSTEM_CONFIG

TOOL_SPECS: List[ToolSpec] = [
    INSPECT_DATASET,
    LIST_SYSTEM_CONFIG,  # Discovery tool
    LIST_DATASET_FIELDS,  # Discovery tool
    LIST_DATASET_FORMATTERS,  # Discovery tool
    LIST_DATASET_LOAD_STRATEGIES,  # Discovery tool
]

__all__ = ["INSPECT_DATASET", "LIST_DATASET_FIELDS", "LIST_DATASET_FORMATTERS", "LIST_DATASET_LOAD_STRATEGIES", "LIST_SYSTEM_CONFIG", "TOOL_SPECS"]
