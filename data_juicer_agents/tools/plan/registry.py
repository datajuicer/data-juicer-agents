# -*- coding: utf-8 -*-
"""Registry for plan tool specs."""

from __future__ import annotations

from typing import List

from data_juicer_agents.core.tool import ToolSpec

from .assemble_plan.tool import ASSEMBLE_PLAN
from .build_dataset_spec.tool import BUILD_DATASET_SPEC
from .build_process_spec.tool import BUILD_PROCESS_SPEC
from .build_system_spec.tool import BUILD_SYSTEM_SPEC
from .plan_save.tool import PLAN_SAVE
from .plan_validate.tool import PLAN_VALIDATE
from .validate_dataset_spec.tool import VALIDATE_DATASET_SPEC
from .validate_process_spec.tool import VALIDATE_PROCESS_SPEC
from .validate_system_spec.tool import VALIDATE_SYSTEM_SPEC

TOOL_SPECS: List[ToolSpec] = [
    BUILD_DATASET_SPEC,
    BUILD_PROCESS_SPEC,
    BUILD_SYSTEM_SPEC,
    VALIDATE_DATASET_SPEC,
    VALIDATE_PROCESS_SPEC,
    VALIDATE_SYSTEM_SPEC,
    ASSEMBLE_PLAN,
    PLAN_VALIDATE,
    PLAN_SAVE,
]

__all__ = [
    "ASSEMBLE_PLAN",
    "BUILD_DATASET_SPEC",
    "BUILD_PROCESS_SPEC",
    "BUILD_SYSTEM_SPEC",
    "PLAN_SAVE",
    "PLAN_VALIDATE",
    "TOOL_SPECS",
    "VALIDATE_DATASET_SPEC",
    "VALIDATE_PROCESS_SPEC",
    "VALIDATE_SYSTEM_SPEC",
]
