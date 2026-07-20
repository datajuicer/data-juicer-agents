# -*- coding: utf-8 -*-
"""Input models for submit_ray_job."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SubmitRayJobInput(BaseModel):
    plan_path: str = Field(description="Plan YAML path to submit.")
    ray_address: Optional[str] = Field(
        default=None,
        description="Ray Job API address (HTTP). If omitted, uses RAY_ADDRESS env var.",
    )
    timeout: int = Field(default=600, ge=1, description="Job execution timeout in seconds.")
    no_wait: bool = Field(
        default=False,
        description="If true, submit and return immediately without tailing logs.",
    )
    confirm: bool = Field(
        default=False,
        description="Explicit confirmation required before submission.",
    )


class SubmitRayJobOutput(BaseModel):
    ok: bool = True
