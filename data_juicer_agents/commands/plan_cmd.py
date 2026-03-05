# -*- coding: utf-8 -*-
"""Implementation for `djx plan`."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

import yaml

from data_juicer_agents.capabilities.plan.diff import build_plan_diff
from data_juicer_agents.capabilities.plan.service import (
    PlanUseCase,
    PlanningMode,
    default_workflows_dir,
)
from data_juicer_agents.capabilities.plan.schema import PlanModel
from data_juicer_agents.capabilities.plan.validation import PlanValidator
from data_juicer_agents.capabilities.trace.repository import TraceStore
from data_juicer_agents.commands.output_control import emit, emit_json, enabled


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _resolve_llm_review_flag(args: Any) -> bool:
    value = getattr(args, "llm_review", None)
    if isinstance(value, bool):
        return value
    return _env_flag("DJA_ENABLE_LLM_REVIEW", False)


def _print_plan_diff(diff: dict) -> None:
    field_changes = diff.get("field_changes", {})
    metadata_changes = diff.get("metadata_changes", {})
    operators = diff.get("operators", {})

    if not field_changes and not metadata_changes and not operators.get("added") and not operators.get("removed") and not operators.get("order_changed"):
        print("Plan diff: no effective changes")
        return

    print("Plan diff:")
    for key, item in field_changes.items():
        print(f"- {key}: {item.get('old')} -> {item.get('new')}")
    for op in operators.get("added", []):
        print(f"- operators added: {op.get('name')}")
    for op in operators.get("removed", []):
        print(f"- operators removed: {op.get('name')}")
    if operators.get("order_changed"):
        print("- operators order changed")
    for key in metadata_changes.keys():
        print(f"- {key} updated")


def _infer_error_code(error_text: str) -> str:
    text = str(error_text or "").lower()
    if "--dataset and --export are required" in text:
        return "missing_dataset_export"
    if "--from-run-id requires --base-plan" in text:
        return "missing_base_plan_for_run"
    if "base plan file not found" in text:
        return "base_plan_not_found"
    if "run not found" in text:
        return "run_not_found"
    if "conflict" in text:
        return "conflict_args"
    if "unknown template" in text:
        return "template_not_found"
    if "template retrieve failed" in text:
        return "template_retrieve_no_match"
    if "output must" in text or "json object" in text:
        return "llm_output_invalid"
    if "validation failed" in text:
        return "plan_validation_failed"
    if "llm" in text:
        return "llm_call_failed"
    return "unknown"


def _next_actions_for_error(code: str) -> List[str]:
    mapping = {
        "missing_dataset_export": [
            "Provide dataset_path and export_path.",
            "Or pass --base-plan for revision mode.",
        ],
        "missing_base_plan_for_run": [
            "Provide --base-plan together with --from-run-id.",
        ],
        "base_plan_not_found": [
            "Check base plan path and retry.",
        ],
        "run_not_found": [
            "Check run_id via djx trace --plan-id <plan_id>.",
        ],
        "conflict_args": [
            "Remove conflicting flags and retry planning.",
        ],
        "template_not_found": [
            "Use djx templates to list valid template names.",
            "Or remove --from-template and use full-llm mode.",
        ],
        "template_retrieve_no_match": [
            "Try --from-template with a known template.",
            "Or fallback to full-llm planning.",
        ],
        "plan_validation_failed": [
            "Adjust intent/constraints and regenerate plan.",
            "Run djx retrieve first to ground operator choices.",
        ],
        "llm_output_invalid": [
            "Retry planning with stricter intent constraints.",
            "Inspect operator names/params and regenerate.",
        ],
        "llm_call_failed": [
            "Check API key/base URL/model settings.",
            "Retry with a clearer intent.",
        ],
        "unknown": [
            "Inspect error message and retry.",
        ],
    }
    return list(mapping.get(code, mapping["unknown"]))


def _error_result(
    message: str,
    *,
    exit_code: int = 2,
    error_type: str = "plan_failed",
    stage: str | None = None,
    attempts: List[Dict[str, Any]] | None = None,
    fallback_messages: List[str] | None = None,
    recoverable: bool = True,
) -> Dict[str, Any]:
    code = _infer_error_code(message)
    return {
        "ok": False,
        "exit_code": int(exit_code),
        "error_type": error_type,
        "error_code": code,
        "message": str(message),
        "stage": stage,
        "recoverable": bool(recoverable),
        "attempts": list(attempts or []),
        "fallback_messages": list(fallback_messages or []),
        "next_actions": _next_actions_for_error(code),
    }


def execute_plan(args) -> Dict[str, Any]:
    base_plan = None
    if args.base_plan:
        base_path = Path(args.base_plan)
        if not base_path.exists():
            return _error_result(
                f"Base plan file not found: {base_path}",
                error_type="base_plan_error",
                stage="input_validation",
                recoverable=False,
            )
        with open(base_path, "r", encoding="utf-8") as f:
            base_plan = PlanModel.from_dict(yaml.safe_load(f))

    from_template = str(getattr(args, "from_template", "") or "").strip() or None
    template_retrieve = bool(getattr(args, "template_retrieve", False))

    if base_plan is not None and from_template:
        return _error_result(
            "Conflict: --base-plan cannot be used with --from-template.",
            stage="input_validation",
            recoverable=False,
        )
    if base_plan is not None and template_retrieve:
        return _error_result(
            "Conflict: --base-plan cannot be used with --template-retrieve.",
            stage="input_validation",
            recoverable=False,
        )
    ignored_template_retrieve = False
    if from_template and template_retrieve:
        ignored_template_retrieve = True
        template_retrieve = False

    dataset_path = args.dataset
    export_path = args.export
    custom_operator_paths = list(args.custom_operator_paths or [])
    if base_plan is not None:
        if not dataset_path:
            dataset_path = base_plan.dataset_path
        if not export_path:
            export_path = base_plan.export_path
        if not custom_operator_paths:
            custom_operator_paths = list(base_plan.custom_operator_paths)
    else:
        if not dataset_path or not export_path:
            return _error_result(
                "--dataset and --export are required when --base-plan is not provided.",
                error_type="missing_required",
                stage="input_validation",
                recoverable=False,
            )

    run_context = None
    if args.from_run_id:
        if base_plan is None:
            return _error_result(
                "--from-run-id requires --base-plan.",
                error_type="missing_required",
                stage="input_validation",
                recoverable=False,
            )
        store = TraceStore()
        run_context = store.get(args.from_run_id)
        if run_context is None:
            return _error_result(
                f"Run not found: {args.from_run_id}",
                error_type="run_not_found",
                stage="input_validation",
                recoverable=False,
            )

    def _new_planner(planning_mode: PlanningMode) -> PlanUseCase:
        return PlanUseCase(
            default_workflows_dir(),
            planning_mode=planning_mode,
            planner_model_name=getattr(args, "planner_model", None),
            llm_api_key=getattr(args, "llm_api_key", None),
            llm_base_url=getattr(args, "llm_base_url", None),
            llm_thinking=getattr(args, "llm_thinking", None),
        )

    attempts_cfg = []
    if base_plan is not None:
        attempts_cfg.append(
            {
                "name": "base-plan",
                "planning_mode": PlanningMode.TEMPLATE_LLM,
                "kwargs": {
                    "base_plan": base_plan,
                    "run_context": run_context,
                    "track_lineage": False,
                },
            }
        )
    elif from_template:
        attempts_cfg.append(
            {
                "name": "from-template",
                "planning_mode": PlanningMode.TEMPLATE_LLM,
                "kwargs": {
                    "from_template": from_template,
                },
            }
        )
    elif template_retrieve:
        attempts_cfg.append(
            {
                "name": "template-retrieve",
                "planning_mode": PlanningMode.TEMPLATE_LLM,
                "kwargs": {
                    "template_retrieve": True,
                },
            }
        )

    attempts_cfg.append(
        {
            "name": "full-llm",
            "planning_mode": PlanningMode.FULL_LLM,
            "kwargs": {},
        }
    )

    review = {"errors": [], "warnings": []}
    include_llm_review = _resolve_llm_review_flag(args)
    attempt_logs: List[Dict[str, Any]] = []
    fallback_messages: List[str] = []
    plan = None
    planner = None

    for idx, attempt in enumerate(attempts_cfg):
        planner = _new_planner(planning_mode=attempt["planning_mode"])
        name = str(attempt["name"])
        log_item: Dict[str, Any] = {
            "name": name,
            "planning_mode": attempt["planning_mode"].value,
            "status": "failed",
            "llm_fallback": False,
            "validation_errors": [],
            "review_errors": [],
            "review_warnings": [],
            "message": "",
            "error_code": "unknown",
            "plan_meta": {},
        }

        try:
            candidate = planner.build_plan(
                user_intent=args.intent,
                dataset_path=dataset_path,
                export_path=export_path,
                custom_operator_paths=custom_operator_paths,
                **dict(attempt.get("kwargs", {})),
            )
            if include_llm_review:
                candidate_review = PlanValidator.llm_review(candidate)
            else:
                candidate_review = {"errors": [], "warnings": []}
            review_errors = list(candidate_review.get("errors", []))
            review_warnings = list(candidate_review.get("warnings", []))
            validation_errors = PlanValidator.validate(candidate)
            errors = validation_errors + review_errors
            log_item["validation_errors"] = validation_errors
            log_item["review_errors"] = review_errors
            log_item["review_warnings"] = review_warnings
            if errors:
                raise ValueError("plan validation failed: " + "; ".join(errors))
            if planner.last_plan_meta.get("llm_fallback") == "true" and name != "full-llm":
                raise ValueError("llm fallback occurred in template-based stage")

            plan = candidate
            review = candidate_review
            log_item.update(
                {
                    "status": "success",
                    "llm_fallback": planner.last_plan_meta.get("llm_fallback") == "true",
                    "plan_meta": dict(planner.last_plan_meta),
                    "message": "plan generated",
                    "error_code": "none",
                }
            )
            attempt_logs.append(log_item)
            break
        except Exception as exc:
            text = str(exc)
            log_item.update(
                {
                    "status": "failed",
                    "llm_fallback": planner.last_plan_meta.get("llm_fallback") == "true",
                    "message": text,
                    "error_code": _infer_error_code(text),
                    "plan_meta": dict(planner.last_plan_meta),
                }
            )
            attempt_logs.append(log_item)

            if idx < len(attempts_cfg) - 1:
                next_name = str(attempts_cfg[idx + 1]["name"])
                fallback_messages.append(f"Warning: {name} planning failed: {text}")
                fallback_messages.append(f"Warning: fallback to {next_name}.")
                continue

            return _error_result(
                f"Plan generation failed: {text}",
                stage=name,
                attempts=attempt_logs,
                fallback_messages=fallback_messages,
            )

    if plan is None or planner is None:
        return _error_result(
            "Plan generation failed: unknown error",
            stage="unknown",
            attempts=attempt_logs,
            fallback_messages=fallback_messages,
        )

    output_path = Path(args.output) if args.output else Path("plans") / f"{plan.plan_id}.yaml"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(plan.to_dict(), f, allow_unicode=False, sort_keys=False)
    except Exception as exc:
        return _error_result(
            f"Plan write failed: {exc}",
            stage="write_plan",
            attempts=attempt_logs,
            fallback_messages=fallback_messages,
        )

    diff = build_plan_diff(base_plan, plan) if base_plan else None

    return {
        "ok": True,
        "exit_code": 0,
        "plan_path": str(output_path),
        "plan": plan.to_dict(),
        "workflow": plan.workflow,
        "operator_names": [op.name for op in plan.operators],
        "review": review,
        "planning_meta": dict(planner.last_plan_meta),
        "plan_diff": diff,
        "attempts": attempt_logs,
        "fallback_messages": fallback_messages,
        "llm_review_enabled": include_llm_review,
        "ignored_template_retrieve": ignored_template_retrieve,
        "warning": (
            "Warning: --from-template is set; ignoring --template-retrieve."
            if ignored_template_retrieve
            else ""
        ),
    }


def run_plan(args) -> int:
    result = execute_plan(args)

    warning = str(result.get("warning", "") or "").strip()
    if warning:
        print(warning)

    for line in result.get("fallback_messages", []):
        print(line)

    if not result.get("ok"):
        print(str(result.get("message", "Plan generation failed")))
        return int(result.get("exit_code", 2))

    output_path = result["plan_path"]
    plan_data = result["plan"]

    print(f"Plan generated: {output_path}")
    print(f"Workflow: {plan_data.get('workflow')}")
    print(f"Operators: {result.get('operator_names', [])}")
    print(f"Revision: {plan_data.get('revision')}")
    if plan_data.get("parent_plan_id"):
        print(f"Parent Plan: {plan_data.get('parent_plan_id')}")
    if plan_data.get("change_summary"):
        print("Change Summary:")
        for line in plan_data.get("change_summary", []):
            print(f"- {line}")

    diff = result.get("plan_diff")
    if isinstance(diff, dict):
        _print_plan_diff(diff)

    planning_meta = result.get("planning_meta", {})
    if enabled(args, "verbose"):
        print(
            "Planning meta: "
            f"strategy={planning_meta.get('strategy')}, "
            f"plan_mode={planning_meta.get('plan_mode')}, "
            f"llm_used={planning_meta.get('llm_used')}, "
            f"llm_fallback={planning_meta.get('llm_fallback')}"
        )

    review = result.get("review", {})
    for item in review.get("warnings", []):
        print(f"Warning: {item}")

    if enabled(args, "debug"):
        emit(args, "Debug planning attempts:", level="debug")
        emit_json(args, result.get("attempts", []), level="debug")
        emit(args, "Debug planning meta payload:", level="debug")
        emit_json(args, planning_meta, level="debug")
        emit(args, "Debug review payload:", level="debug")
        emit_json(args, review, level="debug")

    return int(result.get("exit_code", 0))
