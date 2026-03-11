# -*- coding: utf-8 -*-
"""Deterministic planner core."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from data_juicer_agents.tools.op_manager.operator_registry import (
    get_available_operator_names,
    resolve_operator_name,
)

from .schema import OperatorStep, PlanContext, PlanDraftOperator, PlanDraftSpec, PlanModel
from .validation import validate_plan_schema


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
    def normalize_draft_spec(cls, draft_spec: PlanDraftSpec | Dict[str, Any]) -> PlanDraftSpec:
        if isinstance(draft_spec, PlanDraftSpec):
            source = draft_spec
        elif isinstance(draft_spec, dict):
            source = PlanDraftSpec.from_dict(draft_spec)
        else:
            raise PlannerBuildError("draft_spec must be a dict object")

        available_ops = get_available_operator_names()
        operators: List[PlanDraftOperator] = []
        for item in source.operators:
            raw_name = str(item.name or "").strip()
            if not raw_name:
                continue
            canonical = resolve_operator_name(raw_name, available_ops=available_ops)
            operators.append(
                PlanDraftOperator(
                    name=canonical,
                    params=cls._normalize_params(item.params),
                )
            )

        spec = PlanDraftSpec(
            modality=str(source.modality or "unknown").strip() or "unknown",
            text_keys=cls._normalize_string_list(source.text_keys),
            image_key=(str(source.image_key or "").strip() or None),
            operators=operators,
            risk_notes=cls._normalize_string_list(source.risk_notes),
            estimation=cls._normalize_params(source.estimation),
            approval_required=bool(source.approval_required),
        )
        if not spec.operators:
            raise PlannerBuildError("draft_spec.operators must contain at least one operator")
        return spec

    @staticmethod
    def infer_modality(
        *,
        requested_modality: str,
        text_keys: List[str],
        image_key: str | None,
    ) -> str:
        candidate = str(requested_modality or "").strip().lower()
        if candidate in {"text", "image", "multimodal", "unknown"}:
            if candidate == "unknown":
                pass
            else:
                return candidate
        has_text = bool(text_keys)
        has_image = bool(image_key)
        if has_text and has_image:
            return "multimodal"
        if has_image:
            return "image"
        if has_text:
            return "text"
        return "unknown"

    @classmethod
    def build_plan(
        cls,
        *,
        user_intent: str,
        dataset_path: str,
        export_path: str,
        draft_spec: PlanDraftSpec | Dict[str, Any],
        custom_operator_paths: Iterable[Any] | None = None,
    ) -> PlanModel:
        context = cls.normalize_context(
            user_intent=user_intent,
            dataset_path=dataset_path,
            export_path=export_path,
            custom_operator_paths=custom_operator_paths,
        )
        spec = cls.normalize_draft_spec(draft_spec)

        plan = PlanModel(
            plan_id=PlanModel.new_id(),
            user_intent=context.user_intent,
            dataset_path=context.dataset_path,
            export_path=context.export_path,
            modality=cls.infer_modality(
                requested_modality=spec.modality,
                text_keys=spec.text_keys,
                image_key=spec.image_key,
            ),
            text_keys=list(spec.text_keys),
            image_key=spec.image_key,
            operators=[
                OperatorStep(name=item.name, params=item.params)
                for item in spec.operators
            ],
            risk_notes=list(spec.risk_notes),
            estimation=dict(spec.estimation),
            custom_operator_paths=list(context.custom_operator_paths),
            approval_required=spec.approval_required,
        )
        errors = validate_plan_schema(plan)
        if errors:
            raise PlannerBuildError("; ".join(errors))
        return plan
