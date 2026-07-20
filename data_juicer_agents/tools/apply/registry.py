# -*- coding: utf-8 -*-
"""Registry for apply tool specs."""

from __future__ import annotations

from typing import List

from data_juicer_agents.core.tool import ToolSpec

from .apply_recipe.tool import APPLY_RECIPE
from .submit_ray_job.tool import SUBMIT_RAY_JOB

TOOL_SPECS: List[ToolSpec] = [APPLY_RECIPE, SUBMIT_RAY_JOB]

__all__ = ["APPLY_RECIPE", "SUBMIT_RAY_JOB", "TOOL_SPECS"]
