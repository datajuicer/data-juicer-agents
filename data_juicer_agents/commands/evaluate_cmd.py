# -*- coding: utf-8 -*-
"""Implementation for `djx evaluate`."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from data_juicer_agents.capabilities.apply.service import ApplyUseCase
from data_juicer_agents.capabilities.plan.service import (
    PlanUseCase,
    PlanningMode,
    default_workflows_dir,
    normalize_planning_mode,
)
from data_juicer_agents.capabilities.plan.validation import PlanValidator
from data_juicer_agents.capabilities.trace.repository import TraceStore


def _load_cases(cases_path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(cases_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _execute_with_retries(
    executor: ApplyUseCase,
    plan,
    execute_mode: str,
    timeout: int,
    retries: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], str, str]:
    trace_records: List[Dict[str, Any]] = []
    attempts = 0
    max_attempts = retries + 1

    final_stdout = ""
    final_stderr = ""

    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        trace, returncode, stdout, stderr = executor.execute(
            plan=plan,
            runtime_dir=Path(".djx") / "eval_recipes",
            dry_run=(execute_mode == "dry-run"),
            timeout_seconds=timeout,
        )
        trace_payload = trace.to_dict()
        trace_payload["attempt"] = attempt
        trace_records.append(trace_payload)
        final_stdout, final_stderr = stdout, stderr

        if returncode == 0:
            return (
                {
                    "execution_status": trace.status,
                    "run_id": trace.run_id,
                    "error_type": trace.error_type,
                    "retry_level": trace.retry_level,
                    "attempts": attempts,
                    "success": True,
                },
                trace_records,
                final_stdout,
                final_stderr,
            )

    # Failed after retries.
    last = trace_records[-1]
    return (
        {
            "execution_status": "failed",
            "run_id": last.get("run_id"),
            "error_type": last.get("error_type", "command_failed"),
            "retry_level": last.get("retry_level", "unknown"),
            "attempts": attempts,
            "success": False,
        },
        trace_records,
        final_stdout,
        final_stderr,
    )


def _workflow_match_score(
    expected_workflow: str | None,
    plan_workflow: str | None,
    plan_modality: str | None,
    planning_mode: PlanningMode,
) -> bool:
    if not expected_workflow:
        return True
    if plan_workflow == expected_workflow:
        return True

    # In full_llm mode, workflow is intentionally "custom".
    # Evaluate alignment through inferred modality instead.
    if planning_mode == PlanningMode.FULL_LLM and plan_workflow == "custom":
        if expected_workflow == "rag_cleaning":
            return plan_modality == "text"
        if expected_workflow == "multimodal_dedup":
            return plan_modality in {"multimodal", "image"}
    return False


def _evaluate_one_case(
    idx: int,
    case: Dict[str, Any],
    planning_mode: PlanningMode,
    execute_mode: str,
    include_logs: bool,
    timeout: int,
    retries: int,
) -> Tuple[int, Dict[str, Any], List[Dict[str, Any]]]:
    planner = PlanUseCase(
        default_workflows_dir(),
        planning_mode=planning_mode,
    )
    executor = ApplyUseCase()

    intent = case["intent"]
    dataset_path = case["dataset_path"]
    export_path = case["export_path"]
    expected_workflow = case.get("expected_workflow")

    item: Dict[str, Any] = {
        "index": idx,
        "intent": intent,
        "expected_workflow": expected_workflow,
        "status": "unknown",
        "errors": [],
        "attempts": 0,
    }

    try:
        plan = planner.build_plan(
            user_intent=intent,
            dataset_path=dataset_path,
            export_path=export_path,
            text_keys=case.get("text_keys"),
            image_key=case.get("image_key"),
        )
        errors = PlanValidator.validate(plan)
        if errors:
            item["status"] = "plan_invalid"
            item["errors"] = errors
            return idx, item, []

        item["status"] = "plan_valid"
        item["plan_id"] = plan.plan_id
        item["workflow"] = plan.workflow
        item["modality"] = getattr(plan, "modality", "unknown")

        trace_records: List[Dict[str, Any]] = []
        if execute_mode == "none":
            item["execution_status"] = "skipped"
            item["attempts"] = 0
        else:
            exec_result, trace_records, stdout, stderr = _execute_with_retries(
                executor=executor,
                plan=plan,
                execute_mode=execute_mode,
                timeout=timeout,
                retries=retries,
            )
            item.update(exec_result)
            if not exec_result["success"]:
                item["errors"].append(stderr.strip() or "execution failed")
            if include_logs:
                item["stdout"] = stdout
                item["stderr"] = stderr

        item["task_success"] = _workflow_match_score(
            expected_workflow=expected_workflow,
            plan_workflow=plan.workflow,
            plan_modality=getattr(plan, "modality", "unknown"),
            planning_mode=planning_mode,
        )

        return idx, item, trace_records

    except Exception as exc:
        item["status"] = "planner_error"
        item["errors"] = [str(exc)]
        return idx, item, []


def _append_history(history_path: Path, payload: Dict[str, Any]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _build_failure_buckets(results: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    buckets: Dict[str, int] = {}
    for item in results:
        bucket = None
        status = item.get("status")

        if status == "planner_error":
            bucket = "planner_error"
        elif status == "plan_invalid":
            bucket = "plan_invalid"
        elif item.get("task_success") is False:
            bucket = "misroute"
        elif item.get("execution_status") == "failed":
            error_type = item.get("error_type", "command_failed")
            retry_level = item.get("retry_level", "unknown")
            bucket = f"execution_failed:{error_type}:{retry_level}"

        if bucket:
            buckets[bucket] = buckets.get(bucket, 0) + 1

    ranked = sorted(buckets.items(), key=lambda x: x[1], reverse=True)
    ranked = ranked[:top_k]
    return [{"bucket": key, "count": count} for key, count in ranked]


def _resolve_planning_mode(args) -> PlanningMode:
    raw_mode = getattr(args, "planning_mode", None)
    mode = normalize_planning_mode(raw_mode or "template-llm")
    alias = bool(getattr(args, "llm_full_plan", False))
    if alias and raw_mode is not None and mode != PlanningMode.FULL_LLM:
        raise ValueError(
            "Conflict: --llm-full-plan implies --planning-mode full-llm."
        )
    if alias:
        return PlanningMode.FULL_LLM
    return mode


def run_evaluate(args) -> int:
    if args.timeout <= 0:
        print("timeout must be > 0")
        return 2
    if args.retries < 0:
        print("retries must be >= 0")
        return 2
    if args.jobs <= 0:
        print("jobs must be > 0")
        return 2
    if args.failure_top_k <= 0:
        print("failure-top-k must be > 0")
        return 2
    try:
        planning_mode = _resolve_planning_mode(args)
    except ValueError as exc:
        print(str(exc))
        return 2

    cases_path = Path(args.cases)
    if not cases_path.exists():
        print(f"Cases file not found: {cases_path}")
        return 2

    trace_store = TraceStore()
    cases = _load_cases(cases_path)

    results: List[Dict[str, Any]] = [None] * len(cases)
    all_trace_records: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [
            pool.submit(
                _evaluate_one_case,
                idx,
                case,
                planning_mode,
                args.execute,
                args.include_logs,
                args.timeout,
                args.retries,
            )
            for idx, case in enumerate(cases)
        ]
        for future in as_completed(futures):
            idx, item, trace_records = future.result()
            results[idx] = item
            all_trace_records.extend(trace_records)

    for payload in all_trace_records:
        trace_store.save_raw(payload)

    plan_valid = sum(1 for item in results if item.get("status") == "plan_valid")
    execution_success = sum(
        1
        for item in results
        if item.get("status") == "plan_valid"
        and item.get("execution_status") in {"success", "skipped"}
    )
    task_success = sum(1 for item in results if item.get("task_success") is True)

    total = len(cases)
    retry_used_cases = sum(1 for item in results if int(item.get("attempts", 0)) > 1)
    summary = {
        "total": total,
        "execution_mode": args.execute,
        "planning_mode": planning_mode.value,
        "jobs": args.jobs,
        "retries": args.retries,
        "plan_valid": plan_valid,
        "execution_success": execution_success,
        "task_success": task_success,
        "plan_valid_rate": (plan_valid / total) if total else 0.0,
        "execution_success_rate": (execution_success / total) if total else 0.0,
        "task_success_rate": (task_success / total) if total else 0.0,
        "retry_used_cases": retry_used_cases,
    }

    error_cases = []
    for item in results:
        has_errors = bool(item.get("errors"))
        task_failed = item.get("task_success") is False
        if has_errors or task_failed:
            error_cases.append(item)

    summary["error_case_count"] = len(error_cases)
    summary["failure_buckets_topk"] = _build_failure_buckets(
        results,
        top_k=args.failure_top_k,
    )

    report = {"summary": summary, "results": results}

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = Path(".djx") / "eval_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if args.errors_output:
        errors_path = Path(args.errors_output)
    else:
        errors_path = Path(".djx") / "eval_errors.json"
    errors_path.parent.mkdir(parents=True, exist_ok=True)
    with open(errors_path, "w", encoding="utf-8") as f:
        json.dump(
            {"summary": summary, "error_cases": error_cases},
            f,
            ensure_ascii=False,
            indent=2,
        )

    history_path = (
        Path(args.history_file)
        if args.history_file
        else Path(".djx") / "eval_history.jsonl"
    )
    if not args.no_history:
        history_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cases": str(cases_path),
            "summary": summary,
            "options": {
                "execute": args.execute,
                "timeout": args.timeout,
                "retries": args.retries,
                "jobs": args.jobs,
                "failure_top_k": args.failure_top_k,
                "planning_mode": planning_mode.value,
                "llm_full_plan_alias": bool(args.llm_full_plan),
            },
        }
        _append_history(history_path, history_payload)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Report saved: {out_path}")
    print(f"Error analysis saved: {errors_path}")
    if not args.no_history:
        print(f"History appended: {history_path}")
    return 0
