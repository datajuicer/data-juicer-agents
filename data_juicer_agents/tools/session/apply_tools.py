# -*- coding: utf-8 -*-
"""Session apply tool adapters."""

from __future__ import annotations

from typing import Any, Dict

from data_juicer_agents.tools.apply_tool_api import ApplyUseCase
from data_juicer_agents.tools.planner import PlanValidator

from .runtime import SessionToolRuntime, short_log, to_bool, to_int


def apply_recipe(
    runtime: SessionToolRuntime,
    *,
    plan_path: str = "",
    dry_run: bool = False,
    timeout: int = 300,
    confirm: bool = False,
) -> Dict[str, Any]:
    runtime.debug(
        "tool:apply_recipe "
        f"plan_path={plan_path or runtime.state.plan_path} dry_run={dry_run} timeout={timeout} confirm={confirm}"
    )
    if not to_bool(confirm, False):
        return {
            "ok": False,
            "error_type": "confirmation_required",
            "requires": ["confirm"],
            "message": (
                "apply may execute dj-process and write export output. "
                "Ask user to confirm, then call apply_recipe with confirm=true."
            ),
        }

    resolved_plan = str(plan_path).strip() or (runtime.state.plan_path or "")
    if not resolved_plan:
        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["plan_path"],
            "message": "plan_path is required for apply_recipe",
        }

    plan = runtime.load_plan_model(resolved_plan)
    if plan is None:
        return {
            "ok": False,
            "error_type": "plan_not_found",
            "message": f"failed to load plan file: {resolved_plan}",
        }

    validation_errors = PlanValidator.validate(plan)
    if validation_errors:
        return {
            "ok": False,
            "error_type": "plan_invalid",
            "plan_path": resolved_plan,
            "validation_errors": validation_errors,
            "message": "plan validation failed before apply",
        }

    executor = ApplyUseCase()
    result, code, stdout, stderr = executor.execute(
        plan=plan,
        runtime_dir=runtime.storage_root() / "recipes",
        dry_run=to_bool(dry_run, False),
        timeout_seconds=max(to_int(timeout, 300), 1),
    )

    payload: Dict[str, Any] = {
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
        else:
            payload["error_type"] = "apply_failed"
            payload["message"] = "apply failed"
        return payload

    runtime.state.plan_path = resolved_plan
    runtime.state.draft_plan = plan.to_dict()
    runtime.state.draft_plan_path_hint = resolved_plan
    runtime.state.dataset_path = plan.dataset_path
    runtime.state.export_path = plan.export_path
    runtime.state.custom_operator_paths = list(plan.custom_operator_paths)
    payload.update(
        {
            "message": "apply succeeded",
            "context": runtime.context_payload(),
        }
    )
    return payload


__all__ = ["apply_recipe"]
