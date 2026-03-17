# -*- coding: utf-8 -*-
"""Tool spec for apply_recipe."""

from __future__ import annotations

from pathlib import Path
from typing import List

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec
from data_juicer_agents.utils.runtime_helpers import short_log, to_bool, to_int
import yaml

from .input import ApplyRecipeInput, GenericOutput
from .logic import ApplyUseCase


def _compose_failure_preview(
    *,
    message: str,
    validation_errors: List[str] | None = None,
    stderr: str = "",
    stdout: str = "",
    execution_error_message: str = "",
) -> str:
    parts: List[str] = []
    head = str(message or "").strip()
    if head:
        parts.append(head)
    details = [str(item).strip() for item in (validation_errors or []) if str(item).strip()]
    if details:
        parts.append("; ".join(details[:3]))
    elif str(execution_error_message or "").strip():
        parts.append(str(execution_error_message).strip())
    elif str(stderr or "").strip():
        parts.append(str(stderr).strip())
    elif str(stdout or "").strip():
        parts.append(str(stdout).strip())
    return " | ".join(part for part in parts if part).strip()


def _load_plan_payload(plan_path: str) -> dict | None:
    path = Path(plan_path).expanduser()
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _apply_recipe(ctx: ToolContext, args: ApplyRecipeInput) -> ToolResult:
    if not to_bool(args.confirm, False):
        return ToolResult.failure(
            summary=(
                "apply may execute dj-process and write export output. Ask user to confirm, then call apply_recipe with confirm=true."
            ),
            error_type="confirmation_required",
            data={
                "ok": False,
                "error_type": "confirmation_required",
                "requires": ["confirm"],
                "message": (
                    "apply may execute dj-process and write export output. "
                    "Ask user to confirm, then call apply_recipe with confirm=true."
                ),
                "failure_preview": (
                    "explicit user confirmation is required before apply; "
                    "ask the user to confirm, then call apply_recipe with confirm=true"
                ),
            },
        )

    resolved_plan = args.plan_path.strip()
    if not resolved_plan:
        return ToolResult.failure(
            summary="plan_path is required for apply_recipe",
            error_type="missing_required",
            data={
                "ok": False,
                "error_type": "missing_required",
                "requires": ["plan_path"],
                "message": "plan_path is required for apply_recipe",
                "failure_preview": "plan_path is required for apply_recipe",
            },
        )

    plan_payload = _load_plan_payload(resolved_plan)
    if plan_payload is None:
        return ToolResult.failure(
            summary=f"failed to load plan file: {resolved_plan}",
            error_type="plan_not_found",
            data={
                "ok": False,
                "error_type": "plan_not_found",
                "message": f"failed to load plan file: {resolved_plan}",
                "failure_preview": f"failed to load plan file: {resolved_plan}",
            },
        )

    executor = ApplyUseCase()
    result, code, stdout, stderr = executor.execute(
        plan_payload=plan_payload,
        runtime_dir=ctx.resolve_artifacts_dir() / "recipes",
        dry_run=to_bool(args.dry_run, False),
        timeout_seconds=max(to_int(args.timeout, 300), 1),
    )

    payload = {
        "ok": code == 0,
        "action": "apply",
        "exit_code": code,
        "plan_path": resolved_plan,
        "stdout": short_log(stdout),
        "stderr": short_log(stderr),
        "execution": result.to_dict(),
    }
    if code != 0:
        if code == 130:
            payload["error_type"] = "interrupted"
            payload["message"] = "apply interrupted by user"
            payload["failure_preview"] = "apply interrupted by user"
            return ToolResult.failure(summary="apply interrupted by user", error_type="interrupted", data=payload)
        payload["error_type"] = "apply_failed"
        payload["message"] = "apply failed"
        payload["failure_preview"] = _compose_failure_preview(
            message="apply failed",
            stderr=payload.get("stderr", ""),
            stdout=payload.get("stdout", ""),
            execution_error_message=str(result.error_message or "").strip(),
        )
        return ToolResult.failure(summary="apply failed", error_type="apply_failed", data=payload)

    payload["message"] = "apply succeeded"
    return ToolResult.success(summary="apply succeeded", data=payload)


APPLY_RECIPE = ToolSpec(
    name="apply_recipe",
    description="Execute a plan via dj-process using an explicit plan_path.",
    input_model=ApplyRecipeInput,
    output_model=GenericOutput,
    executor=_apply_recipe,
    tags=("apply", "execute"),
    effects="execute",
    confirmation="required",
)


__all__ = ["APPLY_RECIPE"]
