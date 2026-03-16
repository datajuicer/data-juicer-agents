# -*- coding: utf-8 -*-
"""Pure logic for assemble_plan."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .._shared.schema import DatasetSpec, OperatorStep, PlanContext, PlanModel
from .._shared.dataset_spec import infer_modality
from .._shared.process_spec import normalize_process_spec
from .._shared.system_spec import normalize_system_spec


class PlannerBuildError(ValueError):
    """Raised when planner core cannot build a valid plan."""


class PlannerCore:
    """Pure deterministic planner builder."""

    @staticmethod
    def _normalize_string_list(values: Iterable[Any] | None) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for item in values or []:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            normalized.append(text)
            seen.add(text)
        return normalized

    @staticmethod
    def _normalize_params(value: Any) -> Dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _normalize_optional_text(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

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
            custom_operator_paths=cls._normalize_string_list(custom_operator_paths),
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
    def normalize_dataset_spec(cls, dataset_spec: DatasetSpec | Dict[str, Any]) -> DatasetSpec:
        if isinstance(dataset_spec, DatasetSpec):
            source = dataset_spec
        elif isinstance(dataset_spec, dict):
            source = DatasetSpec.from_dict(dataset_spec)
        else:
            raise PlannerBuildError("dataset_spec must be a dict object")

        return DatasetSpec.from_dict(
            {
                "io": {
                    "dataset_path": str(source.io.dataset_path or "").strip(),
                    "dataset": cls._normalize_params(source.io.dataset) if isinstance(source.io.dataset, dict) else None,
                    "generated_dataset_config": (
                        cls._normalize_params(source.io.generated_dataset_config)
                        if isinstance(source.io.generated_dataset_config, dict)
                        else None
                    ),
                    "export_path": str(source.io.export_path or "").strip(),
                },
                "binding": {
                    "modality": str(source.binding.modality or "unknown").strip() or "unknown",
                    "text_keys": cls._normalize_string_list(source.binding.text_keys),
                    "image_key": cls._normalize_optional_text(source.binding.image_key),
                    "audio_key": cls._normalize_optional_text(source.binding.audio_key),
                    "video_key": cls._normalize_optional_text(source.binding.video_key),
                    "image_bytes_key": cls._normalize_optional_text(source.binding.image_bytes_key),
                },
                "warnings": cls._normalize_string_list(source.warnings),
            }
        )

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
            normalized_dataset = cls.normalize_dataset_spec(dataset_spec)
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
        return PlanModel(
            plan_id=PlanModel.new_id(),
            user_intent=context.user_intent,
            dataset_path=context.dataset_path,
            export_path=context.export_path,
            dataset=normalized_dataset.io.dataset,
            generated_dataset_config=normalized_dataset.io.generated_dataset_config,
            modality=modality,
            text_keys=list(normalized_dataset.binding.text_keys),
            image_key=normalized_dataset.binding.image_key,
            audio_key=normalized_dataset.binding.audio_key,
            video_key=normalized_dataset.binding.video_key,
            image_bytes_key=normalized_dataset.binding.image_bytes_key,
            operators=[OperatorStep(name=item.name, params=item.params) for item in normalized_process.operators],
            risk_notes=cls._normalize_string_list(risk_notes),
            estimation=cls._normalize_params(estimation),
            executor_type=normalized_system.executor_type,
            np=normalized_system.np,
            open_tracer=normalized_system.open_tracer,
            open_monitor=normalized_system.open_monitor,
            use_cache=normalized_system.use_cache,
            skip_op_error=normalized_system.skip_op_error,
            custom_operator_paths=list(normalized_system.custom_operator_paths),
            warnings=cls._normalize_string_list(
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
    return {
        "ok": True,
        "plan": plan.to_dict(),
        "plan_id": plan.plan_id,
        "operator_names": [item.name for item in plan.operators],
        "modality": plan.modality,
        "warnings": list(plan.warnings),
    }


__all__ = ["PlannerBuildError", "PlannerCore", "assemble_plan"]
