# -*- coding: utf-8 -*-
"""Minimal hard orchestration for `djx plan`."""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List

from data_juicer_agents.tools.op_manager.retrieval_service import (
    extract_candidate_names,
    retrieve_operator_candidates,
)
from data_juicer_agents.tools.planner import PlanValidator, PlannerCore

from .generator import PlanDraftGenerator


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
        self.generator = PlanDraftGenerator(
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
        top_k: int = 12,
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
            dataset_path=dataset_path,
        )

    def generate_plan(
        self,
        *,
        user_intent: str,
        dataset_path: str,
        export_path: str,
        custom_operator_paths: Iterable[Any] | None = None,
        retrieved_candidates: Dict[str, Any] | None = None,
        retrieval_top_k: int = 12,
        retrieval_mode: str = "auto",
    ) -> Dict[str, Any]:
        retrieval = self._resolve_retrieval(
            user_intent=user_intent,
            dataset_path=dataset_path,
            top_k=retrieval_top_k,
            mode=retrieval_mode,
            retrieved_candidates=retrieved_candidates,
        )
        draft_spec = self.generator.generate(
            user_intent=user_intent,
            dataset_path=dataset_path,
            export_path=export_path,
            retrieval_payload=retrieval,
        )
        plan = PlannerCore.build_plan(
            user_intent=user_intent,
            dataset_path=dataset_path,
            export_path=export_path,
            draft_spec=draft_spec,
            custom_operator_paths=custom_operator_paths,
        )
        validation_errors = PlanValidator.validate(plan)
        if validation_errors:
            raise ValueError("plan validation failed: " + "; ".join(validation_errors))

        return {
            "plan": plan,
            "draft_spec": draft_spec.to_dict(),
            "retrieval": retrieval,
            "planning_meta": {
                "planner_model": self.generator.model_name,
                "retrieval_source": str(retrieval.get("retrieval_source", "")).strip() or "unknown",
                "retrieval_candidate_count": str(len(extract_candidate_names(retrieval))),
            },
        }


__all__ = ["PlanOrchestrator"]
