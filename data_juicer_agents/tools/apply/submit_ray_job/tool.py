# -*- coding: utf-8 -*-
"""Tool spec binding for submit_ray_job."""

from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import SubmitRayJobInput, SubmitRayJobOutput
from .logic import submit_ray_job


def _submit_ray_job(_ctx: ToolContext, args: SubmitRayJobInput) -> ToolResult:
    if not args.confirm:
        return ToolResult.failure(
            summary=(
                "submit_ray_job will send a job to the remote Ray cluster. "
                "Ask user to confirm, then call submit_ray_job with confirm=true."
            ),
            error_type="confirmation_required",
            data={
                "ok": False,
                "error_type": "confirmation_required",
                "requires": ["confirm"],
                "message": (
                    "submit_ray_job will send a job to the remote Ray cluster. "
                    "Ask user to confirm, then call submit_ray_job with confirm=true."
                ),
            },
        )

    payload = submit_ray_job(
        plan_path=args.plan_path.strip(),
        ray_address=args.ray_address,
        timeout_seconds=max(args.timeout, 1),
        no_wait=args.no_wait,
    )

    if payload.get("ok"):
        return ToolResult.success(
            summary=str(payload.get("message", "Ray job submitted")),
            data=payload,
        )
    return ToolResult.failure(
        summary=str(payload.get("message", "Ray job submission failed")),
        error_type=str(payload.get("error_type", "submission_failed")),
        data=payload,
    )


SUBMIT_RAY_JOB = ToolSpec(
    name="submit_ray_job",
    description=(
        "Submit a Data-Juicer processing plan to a remote Ray cluster via the Ray Job API. "
        "The plan's recipe is written with executor_type=ray (single-machine dedup ops are "
        "auto-rewritten to their ray-native variants) and submitted via "
        "`ray job submit -- dj-process --config <recipe>.yaml`. Dataset and export paths in "
        "the recipe should be accessible to the Ray Workers (e.g. a shared/mounted filesystem). "
        "Requires RAY_ADDRESS env var or an explicit ray_address parameter."
    ),
    input_model=SubmitRayJobInput,
    output_model=SubmitRayJobOutput,
    executor=_submit_ray_job,
    tags=("apply", "execute", "ray", "distributed"),
    effects="external",
    confirmation="required",
)


__all__ = ["SUBMIT_RAY_JOB"]
