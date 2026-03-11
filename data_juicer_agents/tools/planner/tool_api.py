# -*- coding: utf-8 -*-
"""Planner APIs exposed to agent tools."""

from __future__ import annotations

import json
from typing import Any, Dict

from .core import PlannerBuildError, PlannerCore
from .schema import PlanModel
from .validation import PlanValidator


def _load_json_object(raw: str, *, field_name: str) -> Dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        raise PlannerBuildError(f"{field_name} is required")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlannerBuildError(f"{field_name} must be valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PlannerBuildError(f"{field_name} must decode to a JSON object")
    return payload


def plan_build(
    *,
    user_intent: str,
    dataset_path: str,
    export_path: str,
    draft_spec: Dict[str, Any],
    custom_operator_paths: Any = None,
) -> Dict[str, Any]:
    plan = PlannerCore.build_plan(
        user_intent=user_intent,
        dataset_path=dataset_path,
        export_path=export_path,
        draft_spec=draft_spec,
        custom_operator_paths=custom_operator_paths,
    )
    return {
        "ok": True,
        "plan": plan.to_dict(),
        "plan_id": plan.plan_id,
        "operator_names": [item.name for item in plan.operators],
        "modality": plan.modality,
    }


def plan_build_from_json(
    *,
    user_intent: str,
    dataset_path: str,
    export_path: str,
    draft_spec_json: str,
    custom_operator_paths: Any = None,
) -> Dict[str, Any]:
    try:
        payload = _load_json_object(draft_spec_json, field_name="draft_spec_json")
        return plan_build(
            user_intent=user_intent,
            dataset_path=dataset_path,
            export_path=export_path,
            draft_spec=payload,
            custom_operator_paths=custom_operator_paths,
        )
    except PlannerBuildError as exc:
        return {
            "ok": False,
            "error_type": "plan_build_invalid",
            "message": str(exc),
        }


def plan_validate(*, plan_payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        plan = PlanModel.from_dict(plan_payload)
    except Exception as exc:
        return {
            "ok": False,
            "error_type": "plan_invalid_payload",
            "message": f"failed to load plan payload: {exc}",
        }

    errors = PlanValidator.validate(plan)
    return {
        "ok": len(errors) == 0,
        "plan_id": plan.plan_id,
        "operator_names": [item.name for item in plan.operators],
        "validation_errors": errors,
        "message": "plan is valid" if not errors else "plan validation failed",
    }
