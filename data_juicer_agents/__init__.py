# -*- coding: utf-8 -*-
"""Data-Juicer-Agents package."""

from importlib.metadata import PackageNotFoundError, version

from data_juicer_agents.capabilities import ApplyUseCase
from data_juicer_agents.tools.plan import PlanModel, PlanValidator, validate_plan_schema

try:
    __version__ = version("data-juicer-agents")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "PlanValidator",
    "ApplyUseCase",
    "PlanModel",
    "validate_plan_schema",
    "__version__",
]
