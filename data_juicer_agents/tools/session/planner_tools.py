# -*- coding: utf-8 -*-
"""Session planner tools backed by the deterministic planner core."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from data_juicer_agents.tools.planner import PlanModel, plan_build_from_json, plan_validate as validate_plan_payload

from .runtime import SessionToolRuntime, to_bool, to_string_list


def plan_build(
    runtime: SessionToolRuntime,
    *,
    intent: str,
    dataset_path: str = "",
    export_path: str = "",
    custom_operator_paths: Any = None,
    draft_spec_json: str = "",
) -> Dict[str, Any]:
    runtime.debug(
        "tool:plan_build "
        f"intent={intent!r} dataset_path={dataset_path or runtime.state.dataset_path} "
        f"export_path={export_path or runtime.state.export_path}"
    )
    resolved_intent = str(intent).strip()
    resolved_dataset = str(dataset_path).strip() or (runtime.state.dataset_path or "")
    resolved_export = str(export_path).strip() or (runtime.state.export_path or "")
    resolved_custom_paths = to_string_list(custom_operator_paths) or list(runtime.state.custom_operator_paths)

    missing = [
        field
        for field, value in {
            "intent": resolved_intent,
            "dataset_path": resolved_dataset,
            "export_path": resolved_export,
            "draft_spec_json": str(draft_spec_json).strip(),
        }.items()
        if not value
    ]
    if missing:
        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": missing,
            "message": "intent, dataset_path, export_path, and draft_spec_json are required for plan_build",
        }

    result = plan_build_from_json(
        user_intent=resolved_intent,
        dataset_path=resolved_dataset,
        export_path=resolved_export,
        draft_spec_json=str(draft_spec_json),
        custom_operator_paths=resolved_custom_paths,
    )
    if not result.get("ok"):
        return result

    plan_data = result["plan"]
    runtime.state.dataset_path = resolved_dataset
    runtime.state.export_path = resolved_export
    runtime.state.plan_path = None
    runtime.state.draft_plan = plan_data
    runtime.state.draft_plan_path_hint = None
    if resolved_custom_paths:
        runtime.state.custom_operator_paths = list(resolved_custom_paths)

    return {
        "ok": True,
        "action": "plan_build",
        "message": "plan draft built",
        "plan_id": str(result.get("plan_id", "")).strip(),
        "modality": str(result.get("modality", "")).strip(),
        "operator_names": list(result.get("operator_names", [])),
        "plan": plan_data,
        "requires_save": True,
        "context": runtime.context_payload(),
    }


def _resolve_plan_for_validation(
    runtime: SessionToolRuntime,
    *,
    plan_path: str,
    use_draft: bool,
) -> tuple[PlanModel | None, str, List[str], Dict[str, Any] | None]:
    resolved_path = str(plan_path).strip()
    plan = None
    plan_source = "draft"
    warnings: List[str] = []

    if resolved_path:
        plan = runtime.load_plan_model(resolved_path)
        if plan is not None:
            plan_source = "path"
            runtime.state.draft_plan = plan.to_dict()
            runtime.state.draft_plan_path_hint = resolved_path
        elif runtime.looks_like_plan_id(resolved_path):
            draft = runtime.current_draft_plan_model()
            if draft is not None and str(draft.plan_id).strip() == resolved_path:
                plan = draft
                plan_source = "draft_by_plan_id"
                warnings.append(
                    f"plan_path={resolved_path} is a plan_id token; using current draft plan"
                )
            else:
                resolved_by_id = runtime.find_saved_plan_path_by_plan_id(resolved_path)
                if resolved_by_id:
                    plan = runtime.load_plan_model(resolved_by_id)
                    if plan is not None:
                        plan_source = "resolved_path_by_plan_id"
                        runtime.state.draft_plan = plan.to_dict()
                        runtime.state.draft_plan_path_hint = resolved_by_id
                        warnings.append(
                            f"plan_path={resolved_path} treated as plan_id; resolved to {resolved_by_id}"
                        )
        if plan is None:
            if use_draft:
                warnings.append(
                    f"failed to load plan file: {resolved_path}; fallback to draft plan"
                )
                plan = runtime.current_draft_plan_model()
                if plan is not None:
                    plan_source = "draft_fallback"
                elif runtime.state.plan_path:
                    plan = runtime.load_plan_model(runtime.state.plan_path)
                    if plan is not None:
                        plan_source = "saved_plan_fallback"
                        runtime.state.draft_plan = plan.to_dict()
                        runtime.state.draft_plan_path_hint = runtime.state.plan_path
            else:
                return None, plan_source, warnings, {
                    "ok": False,
                    "error_type": "plan_not_found",
                    "message": f"failed to load plan file: {resolved_path}",
                }
    elif use_draft:
        plan = runtime.current_draft_plan_model()
        if plan is None and runtime.state.plan_path:
            plan = runtime.load_plan_model(runtime.state.plan_path)
            plan_source = "saved_plan"
            if plan is not None:
                runtime.state.draft_plan = plan.to_dict()
                runtime.state.draft_plan_path_hint = runtime.state.plan_path

    if plan is None:
        if resolved_path:
            return None, plan_source, warnings, {
                "ok": False,
                "error_type": "plan_not_found",
                "message": (
                    f"failed to load plan file: {resolved_path}; "
                    "no draft plan available for fallback"
                ),
            }
        return None, plan_source, warnings, {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["plan_path_or_draft"],
            "message": "no plan available to validate; run plan_build first or provide plan_path",
        }

    return plan, plan_source, warnings, None


def plan_validate(
    runtime: SessionToolRuntime,
    *,
    plan_path: str = "",
    use_draft: bool = True,
) -> Dict[str, Any]:
    runtime.debug(f"tool:plan_validate plan_path={plan_path or ''} use_draft={use_draft}")
    plan, plan_source, warnings, error = _resolve_plan_for_validation(
        runtime,
        plan_path=plan_path,
        use_draft=to_bool(use_draft, True),
    )
    if error is not None:
        return error
    assert plan is not None

    validation = validate_plan_payload(plan_payload=plan.to_dict())
    return {
        "ok": bool(validation.get("ok")),
        "action": "plan_validate",
        "plan_source": plan_source,
        "plan_id": plan.plan_id,
        "modality": plan.modality,
        "operator_names": [item.name for item in plan.operators],
        "validation_errors": list(validation.get("validation_errors", [])),
        "warnings": warnings,
        "error_count": len(validation.get("validation_errors", [])),
        "message": str(validation.get("message", "plan validation failed")),
        "context": runtime.context_payload(),
    }


def plan_save(
    runtime: SessionToolRuntime,
    *,
    output_path: str = "",
    overwrite: bool = False,
    source_plan_path: str = "",
) -> Dict[str, Any]:
    runtime.debug(
        "tool:plan_save "
        f"output_path={output_path or runtime.state.draft_plan_path_hint or runtime.state.plan_path} "
        f"overwrite={overwrite} source_plan_path={source_plan_path or ''}"
    )
    source_path = str(source_plan_path).strip()
    plan = None
    warnings: List[str] = []
    if source_path:
        plan = runtime.load_plan_model(source_path)
        if plan is None and runtime.looks_like_plan_id(source_path):
            draft = runtime.current_draft_plan_model()
            if draft is not None and str(draft.plan_id).strip() == source_path:
                plan = draft
                warnings.append(
                    f"source_plan_path={source_path} is a plan_id token; using current draft plan"
                )
            else:
                resolved_by_id = runtime.find_saved_plan_path_by_plan_id(source_path)
                if resolved_by_id:
                    plan = runtime.load_plan_model(resolved_by_id)
                    if plan is not None:
                        runtime.state.draft_plan = plan.to_dict()
                        runtime.state.draft_plan_path_hint = resolved_by_id
                        warnings.append(
                            f"source_plan_path={source_path} treated as plan_id; resolved to {resolved_by_id}"
                        )
        if plan is None:
            return {
                "ok": False,
                "error_type": "plan_not_found",
                "message": f"failed to load plan file: {source_path}",
            }
        runtime.state.draft_plan = plan.to_dict()
        runtime.state.draft_plan_path_hint = source_path
    else:
        plan = runtime.current_draft_plan_model()
        if plan is None and runtime.state.plan_path:
            plan = runtime.load_plan_model(runtime.state.plan_path)

    if plan is None:
        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["draft_plan_or_source_plan_path"],
            "message": "no plan draft available to save",
        }

    resolved_output = (
        str(output_path).strip()
        or runtime.state.draft_plan_path_hint
        or runtime.state.plan_path
        or runtime.next_session_plan_path()
    )
    out_path = Path(resolved_output).expanduser()
    if out_path.exists() and not to_bool(overwrite, False):
        return {
            "ok": False,
            "error_type": "file_exists",
            "message": f"output path exists: {out_path}; set overwrite=true to replace",
        }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(plan.to_dict(), handle, allow_unicode=False, sort_keys=False)

    runtime.state.plan_path = str(out_path)
    runtime.state.draft_plan = plan.to_dict()
    runtime.state.draft_plan_path_hint = str(out_path)
    runtime.state.dataset_path = plan.dataset_path
    runtime.state.export_path = plan.export_path
    runtime.state.custom_operator_paths = list(plan.custom_operator_paths)

    return {
        "ok": True,
        "action": "plan_save",
        "plan_path": str(out_path),
        "plan_id": plan.plan_id,
        "modality": plan.modality,
        "operator_names": [item.name for item in plan.operators],
        "message": f"plan saved: {out_path}",
        "warnings": warnings,
        "context": runtime.context_payload(),
    }


__all__ = ["plan_build", "plan_save", "plan_validate"]
