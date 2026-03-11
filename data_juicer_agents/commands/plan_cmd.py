# -*- coding: utf-8 -*-
"""Implementation for `djx plan`."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from data_juicer_agents.capabilities.plan.service import PlanOrchestrator
from data_juicer_agents.commands.output_control import emit, emit_json, enabled


def _error_result(
    message: str,
    *,
    exit_code: int = 2,
    error_type: str = "plan_failed",
    stage: str | None = None,
) -> Dict[str, Any]:
    return {
        "ok": False,
        "exit_code": int(exit_code),
        "error_type": error_type,
        "message": str(message),
        "stage": stage,
    }


def execute_plan(args) -> Dict[str, Any]:
    dataset_path = str(getattr(args, "dataset", "") or "").strip()
    export_path = str(getattr(args, "export", "") or "").strip()
    if not dataset_path or not export_path:
        return _error_result(
            "--dataset and --export are required.",
            error_type="missing_required",
            stage="input_validation",
        )

    custom_operator_paths = list(getattr(args, "custom_operator_paths", []) or [])
    orchestrator = PlanOrchestrator(
        planner_model_name=getattr(args, "planner_model", None),
        llm_api_key=getattr(args, "llm_api_key", None),
        llm_base_url=getattr(args, "llm_base_url", None),
        llm_thinking=getattr(args, "llm_thinking", None),
    )

    try:
        payload = orchestrator.generate_plan(
            user_intent=str(args.intent).strip(),
            dataset_path=dataset_path,
            export_path=export_path,
            custom_operator_paths=custom_operator_paths,
        )
    except Exception as exc:
        return _error_result(
            f"Plan generation failed: {exc}",
            stage="plan_build",
        )

    plan = payload["plan"]
    output_path = Path(args.output) if getattr(args, "output", None) else Path("plans") / f"{plan.plan_id}.yaml"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(output_path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(plan.to_dict(), handle, allow_unicode=False, sort_keys=False)
    except Exception as exc:
        return _error_result(
            f"Plan write failed: {exc}",
            error_type="plan_write_failed",
            stage="write_plan",
        )

    return {
        "ok": True,
        "exit_code": 0,
        "plan_path": str(output_path),
        "plan": plan.to_dict(),
        "operator_names": [op.name for op in plan.operators],
        "planning_meta": payload.get("planning_meta", {}),
        "retrieval": payload.get("retrieval", {}),
        "draft_spec": payload.get("draft_spec", {}),
    }


def run_plan(args) -> int:
    result = execute_plan(args)
    if not result.get("ok"):
        print(str(result.get("message", "Plan generation failed")))
        return int(result.get("exit_code", 2))

    plan_data = result["plan"]
    print(f"Plan generated: {result['plan_path']}")
    print(f"Modality: {plan_data.get('modality')}")
    print(f"Operators: {result.get('operator_names', [])}")

    if enabled(args, "verbose"):
        planning_meta = result.get("planning_meta", {})
        print(
            "Planning meta: "
            f"planner_model={planning_meta.get('planner_model')}, "
            f"retrieval_source={planning_meta.get('retrieval_source')}, "
            f"retrieval_candidate_count={planning_meta.get('retrieval_candidate_count')}"
        )

    if enabled(args, "debug"):
        emit(args, "Debug retrieval payload:", level="debug")
        emit_json(args, result.get("retrieval", {}), level="debug")
        emit(args, "Debug draft spec:", level="debug")
        emit_json(args, result.get("draft_spec", {}), level="debug")
        emit(args, "Debug planning meta:", level="debug")
        emit_json(args, result.get("planning_meta", {}), level="debug")

    return int(result.get("exit_code", 0))
