# -*- coding: utf-8 -*-
"""Input models for plan_validate."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class PlanValidateInput(BaseModel):
    plan_payload: Dict[str, Any] = Field(
        description="Full plan object returned by assemble_plan or loaded from a plan YAML file.",
    )
