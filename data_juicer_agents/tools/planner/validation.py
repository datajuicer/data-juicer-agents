# -*- coding: utf-8 -*-
"""Deterministic planner validation."""

from __future__ import annotations

from pathlib import Path
from typing import List

from data_juicer_agents.tools.op_manager.operator_registry import get_available_operator_names

from .schema import PlanModel


_ALLOWED_MODALITIES = {"text", "image", "multimodal", "unknown"}


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
        errors.append("modality must be one of text/image/multimodal/unknown")
    if not isinstance(plan.custom_operator_paths, list):
        errors.append("custom_operator_paths must be an array")
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
    if plan.modality == "multimodal":
        if not plan.text_keys:
            errors.append("multimodal modality requires text_keys")
        if not plan.image_key:
            errors.append("multimodal modality requires image_key")
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

        available_ops = get_available_operator_names()
        if available_ops:
            for op in plan.operators:
                if op.name not in available_ops:
                    errors.append(
                        f"unsupported operator '{op.name}'; not found in installed Data-Juicer operators"
                    )

        return errors
