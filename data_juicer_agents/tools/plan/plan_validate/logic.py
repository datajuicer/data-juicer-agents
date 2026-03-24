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
    if not plan.recipe:
        errors.append("recipe is required")
    if plan.modality not in _ALLOWED_MODALITIES:
        errors.append("modality must be one of text/image/audio/video/multimodal/unknown")
    if not isinstance(plan.warnings, list):
        errors.append("warnings must be an array")
    if plan.modality == "text" and not plan.recipe.get("text_keys"):
        errors.append("text modality requires text_keys")
    if plan.modality == "image" and not plan.recipe.get("image_key"):
        errors.append("image modality requires image_key")
    if plan.modality == "audio" and not plan.recipe.get("audio_key"):
        errors.append("audio modality requires audio_key")
    if plan.modality == "video" and not plan.recipe.get("video_key"):
        errors.append("video modality requires video_key")
    if plan.modality == "multimodal":
        active = sum([bool(plan.recipe.get("text_keys")), bool(plan.recipe.get("image_key")), bool(plan.recipe.get("audio_key")), bool(plan.recipe.get("video_key"))])
        if active < 2:
            errors.append("multimodal modality requires at least two bound modalities")
    return errors

def validate_recipe_with_dj(recipe: Dict[str, Any]) -> List[str]:
    """Validate the recipe dict using Data-Juicer's native config validation.

    This catches any unknown keys, type mismatches, or constraint violations
    that DJ itself would reject at runtime.
    """
    try:
        from data_juicer_agents.utils.dj_config_bridge import get_dj_config_bridge
        bridge = get_dj_config_bridge()
        is_valid, dj_errors = bridge.validate(recipe)
        if not is_valid:
            return [f"DJ config error: {err}" for err in dj_errors]
    except Exception as exc:
        # DJ not installed or validation unavailable — skip silently
        return [f"DJ validation unavailable: {exc}"]
    return []

class PlanValidator:
    """Validate plan schema and local filesystem preconditions."""

    @staticmethod
    def validate(plan: PlanModel) -> List[str]:
        errors = validate_plan_schema(plan)
        errors.extend(validate_recipe_with_dj(plan.recipe))

        dataset_path_str = plan.recipe.get("dataset_path")
        if not dataset_path_str:
            errors.append("recipe.dataset_path is required")
        else:
            dataset_path = Path(dataset_path_str).expanduser()
            if not dataset_path.exists():
                errors.append(f"dataset_path does not exist: {dataset_path_str}")

        export_path_str = plan.recipe.get("export_path")
        if not export_path_str:
            errors.append("recipe.export_path is required")
        else:
            export_parent = Path(export_path_str).expanduser().resolve().parent
            if not export_parent.exists():
                errors.append(f"export parent directory does not exist: {export_parent}")

        if plan.recipe.get("custom_operator_paths"):
            for raw_path in plan.recipe["custom_operator_paths"]:
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
        "operator_names": list(plan.operator_names),
        "validation_errors": errors,
        "warnings": list(plan.warnings),
        "message": "plan is valid" if not errors else "plan validation failed",
    }


__all__ = ["PlanValidator", "plan_validate", "validate_plan_schema"]
