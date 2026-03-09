# -*- coding: utf-8 -*-
"""Plan validator for schema and execution precondition checks."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from data_juicer_agents.tools.llm_gateway import call_model_json
from data_juicer_agents.tools.op_manager.operator_registry import get_available_operator_names
from data_juicer_agents.capabilities.plan.schema import PlanModel, validate_plan


VALIDATOR_MODEL_NAME = os.environ.get("DJA_VALIDATOR_MODEL", "qwen3-max-2026-01-23")


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


class PlanValidator:
    """Validate plan schema and local filesystem preconditions."""

    @staticmethod
    def validate(plan: PlanModel) -> List[str]:
        errors = validate_plan(plan)

        dataset_path = Path(plan.dataset_path)
        if not dataset_path.exists():
            errors.append(f"dataset_path does not exist: {plan.dataset_path}")

        export_parent = Path(plan.export_path).expanduser().resolve().parent
        if not export_parent.exists():
            errors.append(
                f"export parent directory does not exist: {export_parent}",
            )

        if plan.modality == "text" and not plan.text_keys:
            errors.append("text modality requires text_keys")

        if plan.modality == "image" and not plan.image_key:
            errors.append("image modality requires image_key")

        if plan.modality == "multimodal":
            if not plan.text_keys:
                errors.append("multimodal modality requires text_keys")
            if not plan.image_key:
                errors.append("multimodal modality requires image_key")

        if plan.custom_operator_paths:
            for raw_path in plan.custom_operator_paths:
                path = Path(str(raw_path)).expanduser()
                if not path.exists():
                    errors.append(f"custom_operator_path does not exist: {path}")

        # Validate operator names against installed Data-Juicer operator registry.
        available_ops = get_available_operator_names()
        unknown_ops = []
        if available_ops:
            unknown_ops = [op.name for op in plan.operators if op.name not in available_ops]

        # Only load custom operators when there are unresolved operators.
        if unknown_ops and plan.custom_operator_paths and not errors:
            try:
                from data_juicer.config.config import load_custom_operators

                load_custom_operators([str(item) for item in plan.custom_operator_paths])
                get_available_operator_names.cache_clear()  # type: ignore[attr-defined]
                available_ops = get_available_operator_names()
                unknown_ops = [op.name for op in plan.operators if op.name not in available_ops]
            except Exception as exc:
                errors.append(f"failed to load custom operators: {exc}")

        for op_name in unknown_ops:
            errors.append(
                f"unsupported operator '{op_name}'; not found in installed Data-Juicer operators"
            )

        return errors

    @staticmethod
    def llm_review(
        plan: PlanModel,
        *,
        thinking: bool | None = None,
    ) -> Dict[str, List[str]]:
        """Best-effort semantic review; returns warnings/errors from model."""

        prompt = (
            "You validate Data-Juicer plans for data engineers. "
            "Return JSON only: {errors: string[], warnings: string[]} with concise items. "
            "If no issue, return empty arrays.\n"
            f"Plan JSON:\n{json.dumps(plan.to_dict(), ensure_ascii=False)}"
        )

        try:
            if isinstance(thinking, bool):
                thinking_flag = thinking
            else:
                # Validator thinking is disabled by default for latency.
                thinking_flag = _env_flag("DJA_VALIDATOR_THINKING", False)
            data = call_model_json(
                VALIDATOR_MODEL_NAME,
                prompt,
                thinking=thinking_flag,
            )
            errors = data.get("errors", []) if isinstance(data, dict) else []
            warnings = data.get("warnings", []) if isinstance(data, dict) else []
            if not isinstance(errors, list):
                errors = []
            if not isinstance(warnings, list):
                warnings = []
            return {
                "errors": [str(item) for item in errors],
                "warnings": [str(item) for item in warnings],
            }
        except Exception:
            return {"errors": [], "warnings": []}


@dataclass
class ValidationError:
    """Categorized validation error with suggestion."""
    category: str  # path | operator | combination | config
    field: str
    message: str
    suggestion: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "category": self.category,
            "field": self.field,
            "message": self.message,
            "suggestion": self.suggestion,
        }


def validate_with_suggestions(plan: PlanModel) -> List[ValidationError]:
    """Validate plan and return categorized errors with fix suggestions."""
    errors: List[ValidationError] = []

    # Path validations
    dataset_path = Path(plan.dataset_path)
    if not dataset_path.exists():
        errors.append(ValidationError(
            category="path",
            field="dataset_path",
            message=f"dataset_path does not exist: {plan.dataset_path}",
            suggestion="Provide a valid path to an existing dataset file (e.g., data/dataset.jsonl)",
        ))

    export_parent = Path(plan.export_path).expanduser().resolve().parent
    if not export_parent.exists():
        errors.append(ValidationError(
            category="path",
            field="export_path",
            message=f"export parent directory does not exist: {export_parent}",
            suggestion=f"Create the directory first: mkdir -p {export_parent}",
        ))

    if plan.custom_operator_paths:
        for raw_path in plan.custom_operator_paths:
            path = Path(str(raw_path)).expanduser()
            if not path.exists():
                errors.append(ValidationError(
                    category="path",
                    field="custom_operator_paths",
                    message=f"custom_operator_path does not exist: {path}",
                    suggestion="Provide a valid path to custom operator directory or remove this path",
                ))

    # Config validations
    if plan.modality == "text" and not plan.text_keys:
        errors.append(ValidationError(
            category="config",
            field="text_keys",
            message="text modality requires text_keys",
            suggestion="Specify text_keys field, e.g., ['text'] or ['content']",
        ))

    if plan.modality == "image" and not plan.image_key:
        errors.append(ValidationError(
            category="config",
            field="image_key",
            message="image modality requires image_key",
            suggestion="Specify image_key field, e.g., 'image' or 'images'",
        ))

    if plan.modality == "multimodal":
        if not plan.text_keys:
            errors.append(ValidationError(
                category="config",
                field="text_keys",
                message="multimodal modality requires text_keys",
                suggestion="Specify text_keys field for multimodal data, e.g., ['text']",
            ))
        if not plan.image_key:
            errors.append(ValidationError(
                category="config",
                field="image_key",
                message="multimodal modality requires image_key",
                suggestion="Specify image_key field for multimodal data, e.g., 'image'",
            ))

    # Operator validations
    available_ops = get_available_operator_names()
    unknown_ops: List[str] = []
    if available_ops:
        unknown_ops = [op.name for op in plan.operators if op.name not in available_ops]

    # Try loading custom operators
    if unknown_ops and plan.custom_operator_paths and not errors:
        try:
            from data_juicer.config.config import load_custom_operators
            load_custom_operators([str(item) for item in plan.custom_operator_paths])
            get_available_operator_names.cache_clear()  # type: ignore[attr-defined]
            available_ops = get_available_operator_names()
            unknown_ops = [op.name for op in plan.operators if op.name not in available_ops]
        except Exception as exc:
            errors.append(ValidationError(
                category="operator",
                field="custom_operator_paths",
                message=f"failed to load custom operators: {exc}",
                suggestion="Check custom operator paths and ensure they contain valid Data-Juicer operators",
            ))

    for op_name in unknown_ops:
        errors.append(ValidationError(
            category="operator",
            field="operators",
            message=f"unsupported operator '{op_name}'; not found in installed Data-Juicer operators",
            suggestion=f"Use a valid operator name. Run 'djx retrieve --intent \"{op_name}\"' to find similar operators",
        ))

    # Schema validations
    if not plan.operators:
        errors.append(ValidationError(
            category="config",
            field="operators",
            message="operators list is empty",
            suggestion="Add at least one operator to the plan",
        ))

    if not plan.dataset_path:
        errors.append(ValidationError(
            category="config",
            field="dataset_path",
            message="dataset_path is required",
            suggestion="Specify the input dataset path",
        ))

    if not plan.export_path:
        errors.append(ValidationError(
            category="config",
            field="export_path",
            message="export_path is required",
            suggestion="Specify the output path for processed data",
        ))

    return errors


__all__ = ["PlanValidator", "ValidationError", "validate_with_suggestions"]
