# -*- coding: utf-8 -*-
"""Input models for build_process_spec."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ProcessOperatorInput(BaseModel):
    name: str = Field(description="Canonical operator name.")
    params: Dict[str, Any] = Field(
        description=(
            "Operator-specific params object. Fill suitable concrete params for this operator "
            "based on the user request, dataset context, and retrieve_operators results. "
            "If a threshold, mode, or explicit option is already known, include it here."
        ),
    )


class BuildProcessSpecInput(BaseModel):
    operators: List[ProcessOperatorInput] = Field(
        description=(
            "Ordered operators for this plan. Choose canonical names from retrieve_operators "
            "results and fill appropriate params for each operator."
        ),
    )
