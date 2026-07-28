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
    job_id: str = Field(default="", description="Ray job id (raysubmit_*), empty if unknown.")
    status: str = Field(
        default="",
        description="Final job status: 'succeeded', 'failed', or 'submitted' (no_wait).",
    )
    error_type: Optional[str] = Field(
        default=None, description="Error category when ok is false."
    )
    message: str = Field(default="", description="Human-readable result summary.")
    ray_address: Optional[str] = Field(default=None, description="Ray Job API address used.")
    command: Optional[str] = Field(default=None, description="The `ray job submit` command executed.")
    export_path: Optional[str] = Field(
        default=None,
        description="Per-run uniquified export path (a directory of shards in ray mode).",
    )
    stdout: Optional[str] = Field(default=None, description="Tail of the submission stdout.")
    stderr: Optional[str] = Field(default=None, description="Tail of the submission stderr.")
    duration_seconds: Optional[float] = Field(
        default=None, description="Wall-clock seconds spent on submission/waiting."
    )
