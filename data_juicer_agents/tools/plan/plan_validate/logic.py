# -*- coding: utf-8 -*-
"""Pure logic for plan_validate."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .._shared.schema import PlanModel, _ALLOWED_MODALITIES


def validate_plan_schema(plan: PlanModel) -> List[str]:
    errors: List[str] = []
    if not plan.plan_id:
        errors.append("plan_id is required")
    if not plan.user_intent:
        errors.append("user_intent is required")
    if not plan.dataset_path:
        errors.append("dataset_path is required")
    if not plan.export_path:
        errors.append("export_path is required")
    if plan.modality not in _ALLOWED_MODALITIES:
        errors.append("modality must be one of text/image/audio/video/multimodal/unknown")
    if not isinstance(plan.custom_operator_paths, list):
        errors.append("custom_operator_paths must be an array")
    if not isinstance(plan.warnings, list):
        errors.append("warnings must be an array")
    if not plan.executor_type:
        errors.append("executor_type is required")
    if int(plan.np or 0) <= 0:
        errors.append("np must be >= 1")
    if not plan.operators:
        errors.append("operators must not be empty")
    for idx, op in enumerate(plan.operators):
        if not op.name:
            errors.append(f"operators[{idx}].name is required")
        if not isinstance(op.params, dict):
            errors.append(f"operators[{idx}].params must be an object")
    if plan.modality == "text" and not plan.text_keys:
        errors.append("text modality requires text_keys")
    if plan.modality == "image" and not plan.image_key:
        errors.append("image modality requires image_key")
    if plan.modality == "audio" and not plan.audio_key:
        errors.append("audio modality requires audio_key")
    if plan.modality == "video" and not plan.video_key:
        errors.append("video modality requires video_key")
    if plan.modality == "multimodal":
        active = sum([bool(plan.text_keys), bool(plan.image_key), bool(plan.audio_key), bool(plan.video_key)])
        if active < 2:
            errors.append("multimodal modality requires at least two bound modalities")
    return errors


class PlanValidator:
    """Validate plan schema and local filesystem preconditions."""

    @staticmethod
    def validate(plan: PlanModel) -> List[str]:
        errors = validate_plan_schema(plan)

        dataset_path = Path(plan.dataset_path).expanduser()
        if not dataset_path.exists():
            errors.append(f"dataset_path does not exist: {plan.dataset_path}")

        export_parent = Path(plan.export_path).expanduser().resolve().parent
        if not export_parent.exists():
            errors.append(f"export parent directory does not exist: {export_parent}")

        if plan.custom_operator_paths:
            for raw_path in plan.custom_operator_paths:
                path = Path(str(raw_path)).expanduser()
                if not path.exists():
                    errors.append(f"custom_operator_path does not exist: {path}")

        return errors


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
        "warnings": list(plan.warnings),
        "message": "plan is valid" if not errors else "plan validation failed",
    }


__all__ = ["PlanValidator", "plan_validate", "validate_plan_schema"]
