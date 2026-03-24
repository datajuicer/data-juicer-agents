# -*- coding: utf-8 -*-
"""Pure logic for assemble_plan."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Dict, List

from .._shared.dataset_spec import infer_modality, normalize_dataset_spec
from .._shared.normalize import normalize_params, normalize_string_list
from .._shared.process_spec import normalize_process_spec
from .._shared.schema import DatasetSpec, PlanContext, PlanModel, ProcessSpec, SystemSpec
from .._shared.system_spec import normalize_system_spec


class PlannerBuildError(ValueError):
    """Raised when planner core cannot build a valid plan."""


class PlannerCore:
    """Pure deterministic planner builder."""

    @classmethod
    def normalize_context(
        cls,
        *,
        user_intent: str,
        dataset_path: str,
        export_path: str,
        custom_operator_paths: Iterable[Any] | None = None,
    ) -> PlanContext:
        context = PlanContext(
            user_intent=str(user_intent or "").strip(),
            dataset_path=str(dataset_path or "").strip(),
            export_path=str(export_path or "").strip(),
            custom_operator_paths=normalize_string_list(custom_operator_paths),
        )
        missing = [
            name
            for name, value in {
                "user_intent": context.user_intent,
                "dataset_path": context.dataset_path,
                "export_path": context.export_path,
            }.items()
            if not value
        ]
        if missing:
            raise PlannerBuildError(f"missing required planner context fields: {', '.join(missing)}")
        return context

    @classmethod
    def _build_recipe(
        cls,
        normalized_dataset_spec: DatasetSpec,
        normalized_process_spec: ProcessSpec,
        normalized_system_spec: SystemSpec,
    ) -> Dict[str, Any]:
        """Assemble a DJ-native recipe dict from the three normalized specs."""
        recipe: Dict[str, Any] = {}

        # --- dataset IO fields ---
        recipe["dataset_path"] = normalized_dataset_spec.io.dataset_path
        recipe["export_path"] = normalized_dataset_spec.io.export_path
        if normalized_dataset_spec.io.dataset:
            recipe["dataset"] = dict(normalized_dataset_spec.io.dataset)
        if normalized_dataset_spec.io.generated_dataset_config:
            recipe["generated_dataset_config"] = dict(
                normalized_dataset_spec.io.generated_dataset_config
            )

        # --- dataset binding fields ---
        binding = normalized_dataset_spec.binding
        if binding.text_keys:
            recipe["text_keys"] = list(binding.text_keys)
        if binding.image_key:
            recipe["image_key"] = binding.image_key
        if binding.audio_key:
            recipe["audio_key"] = binding.audio_key
        if binding.video_key:
            recipe["video_key"] = binding.video_key
        if binding.image_bytes_key:
            recipe["image_bytes_key"] = binding.image_bytes_key

        # --- process: DJ-native format [{op_name: params}] ---
        recipe["process"] = [
            {op.name: op.params} for op in normalized_process_spec.operators
        ]

        # --- system fields ---
        system_dict = normalized_system_spec.to_dict()
        # warnings is our internal field, not part of DJ recipe
        system_dict.pop("warnings", None)
        recipe.update(system_dict)

        return recipe

    @classmethod
    def build_plan_from_specs(
        cls,
        *,
        user_intent: str,
        dataset_spec: DatasetSpec | Dict[str, Any],
        process_spec: Dict[str, Any],
        system_spec: Dict[str, Any] | None = None,
        risk_notes: Iterable[Any] | None = None,
        estimation: Dict[str, Any] | None = None,
        approval_required: bool = True,
    ) -> PlanModel:
        try:
            normalized_dataset = normalize_dataset_spec(dataset_spec)
            normalized_process = normalize_process_spec(process_spec)
            normalized_system = normalize_system_spec(
                system_spec,
                custom_operator_paths=_normalized_system_custom_paths(system_spec),
            )
        except ValueError as exc:
            raise PlannerBuildError(str(exc)) from exc

        context = cls.normalize_context(
            user_intent=user_intent,
            dataset_path=normalized_dataset.io.dataset_path,
            export_path=normalized_dataset.io.export_path,
            custom_operator_paths=normalized_system.custom_operator_paths,
        )
        modality = infer_modality(normalized_dataset.binding)
        recipe = cls._build_recipe(normalized_dataset, normalized_process, normalized_system)

        return PlanModel(
            plan_id=PlanModel.new_id(),
            user_intent=context.user_intent,
            modality=modality,
            recipe=recipe,
            risk_notes=normalize_string_list(risk_notes),
            estimation=normalize_params(estimation),
            warnings=normalize_string_list(
                list(normalized_dataset.warnings) + list(normalized_system.warnings)
            ),
            approval_required=bool(approval_required),
        )


def _normalized_system_custom_paths(system_spec: Dict[str, Any] | None) -> List[str]:
    if isinstance(system_spec, dict):
        raw = system_spec.get("custom_operator_paths", [])
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
    return []


def assemble_plan(
    *,
    user_intent: str,
    dataset_spec: Dict[str, Any],
    process_spec: Dict[str, Any],
    system_spec: Dict[str, Any] | None = None,
    approval_required: bool = True,
) -> Dict[str, Any]:
    plan = PlannerCore.build_plan_from_specs(
        user_intent=user_intent,
        dataset_spec=dataset_spec,
        process_spec=process_spec,
        system_spec=system_spec,
        approval_required=approval_required,
    )
    process_steps = plan.recipe.get("process", [])
    operator_names = [
        list(step.keys())[0] for step in process_steps if isinstance(step, dict) and step
    ]
    return {
        "ok": True,
        "plan": plan.to_dict(),
        "plan_id": plan.plan_id,
        "operator_names": operator_names,
        "modality": plan.modality,
        "warnings": list(plan.warnings),
    }


__all__ = ["PlannerBuildError", "PlannerCore", "assemble_plan"]
