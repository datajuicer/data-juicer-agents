# -*- coding: utf-8 -*-
"""Minimal hard orchestration for `djx plan`."""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable

from data_juicer_agents.tools.context import inspect_dataset_schema
from data_juicer_agents.tools.retrieve import (
    extract_candidate_names,
    retrieve_operator_candidates,
)
from data_juicer_agents.tools.plan import (
    PlanModel,
    assemble_plan,
    build_dataset_spec,
    build_process_spec,
    build_system_spec,
    plan_validate,
)

from .generator import ProcessOperatorGenerator


PLANNER_MODEL_NAME = os.environ.get("DJA_PLANNER_MODEL", "qwen3-max-2026-01-23")


def _normalize_candidate_payload(raw_candidates: Any) -> Dict[str, Any] | None:
    if not isinstance(raw_candidates, dict):
        return None
    if not isinstance(raw_candidates.get("candidates", []), list):
        return None
    return raw_candidates


class PlanOrchestrator:
    """Fixed orchestration for CLI plan generation."""

    def __init__(
        self,
        *,
        planner_model_name: str | None = None,
        llm_api_key: str | None = None,
        llm_base_url: str | None = None,
        llm_thinking: bool | None = None,
    ):
        self.generator = ProcessOperatorGenerator(
            model_name=str(planner_model_name or PLANNER_MODEL_NAME).strip() or PLANNER_MODEL_NAME,
            api_key=llm_api_key,
            base_url=llm_base_url,
            thinking=llm_thinking,
        )

    def _resolve_retrieval(
        self,
        *,
        user_intent: str,
        dataset_path: str,
        dataset: Dict[str, Any] | None = None,
        top_k: int = 5,
        mode: str = "auto",
        retrieved_candidates: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        provided = _normalize_candidate_payload(retrieved_candidates)
        if provided is not None:
            return dict(provided)
        return retrieve_operator_candidates(
            intent=user_intent,
            top_k=top_k,
            mode=mode,
            dataset_path=dataset_path or None,
            dataset=dataset,
        )

    def generate_plan(
        self,
        *,
        user_intent: str,
        dataset_path: str,
        export_path: str,
        dataset: Dict[str, Any] | None = None,
        generated_dataset_config: Dict[str, Any] | None = None,
        custom_operator_paths: Iterable[Any] | None = None,
        retrieved_candidates: Dict[str, Any] | None = None,
        retrieval_top_k: int = 5,
        retrieval_mode: str = "auto",
    ) -> Dict[str, Any]:
        retrieval = self._resolve_retrieval(
            user_intent=user_intent,
            dataset_path=dataset_path,
            dataset=dataset,
            top_k=retrieval_top_k,
            mode=retrieval_mode,
            retrieved_candidates=retrieved_candidates,
        )
        # Skip schema probing when a generated dataset is the effective runtime
        # source (highest priority).  Probing a lower-priority dataset_path/dataset
        # would imprint the wrong modality and key bindings into the final plan.
        if generated_dataset_config:
            dataset_profile: Dict[str, Any] = {}
        elif dataset_path or dataset:
            dataset_profile = inspect_dataset_schema(
                dataset_path=dataset_path,
                sample_size=20,
                dataset=dataset,
            )
        else:
            dataset_profile = {}

        dataset_result = build_dataset_spec(
            user_intent=user_intent,
            dataset_path=dataset_path,
            dataset=dataset,
            generated_dataset_config=generated_dataset_config,
            export_path=export_path,
            dataset_profile=dataset_profile,
        )
        if not dataset_result.get("ok"):
            raise ValueError("dataset spec build failed: " + "; ".join(dataset_result.get("validation_errors", []) or [str(dataset_result.get("message", "unknown error"))]))

        operator_payload = self.generator.generate(
            user_intent=user_intent,
            retrieval_payload=retrieval,
            dataset_spec=dataset_result["dataset_spec"],
            dataset_profile=dataset_profile,
        )

        process_result = build_process_spec(
            operators=operator_payload.get("operators", []),
        )
        if not process_result.get("ok"):
            raise ValueError("process spec build failed: " + "; ".join(process_result.get("validation_errors", []) or [str(process_result.get("message", "unknown error"))]))

        system_result = build_system_spec(
            custom_operator_paths=custom_operator_paths,
        )
        if not system_result.get("ok"):
            raise ValueError("system spec build failed: " + "; ".join(system_result.get("validation_errors", []) or [str(system_result.get("message", "unknown error"))]))

        assembled = assemble_plan(
            user_intent=user_intent,
            dataset_spec=dataset_result["dataset_spec"],
            process_spec=process_result["process_spec"],
            system_spec=system_result["system_spec"],
            approval_required=True,
        )
        if not assembled.get("ok"):
            raise ValueError("assemble_plan failed: " + str(assembled.get("message", "unknown error")))

        validation = plan_validate(plan_payload=assembled["plan"])
        if not validation.get("ok"):
            raise ValueError("plan validation failed: " + "; ".join(validation.get("validation_errors", []) or [str(validation.get("message", "unknown error"))]))

        plan = PlanModel.from_dict(assembled["plan"])
        return {
            "plan": plan,
            "dataset_spec": dataset_result["dataset_spec"],
            "process_spec": process_result["process_spec"],
            "system_spec": system_result["system_spec"],
            "retrieval": retrieval,
            "planning_meta": {
                "planner_model": self.generator.model_name,
                "retrieval_source": str(retrieval.get("retrieval_source", "")).strip() or "unknown",
                "retrieval_candidate_count": str(len(extract_candidate_names(retrieval))),
            },
            "validation": validation,
        }


__all__ = ["PlanOrchestrator"]
