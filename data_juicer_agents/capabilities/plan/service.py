# -*- coding: utf-8 -*-
"""Minimal hard orchestration for `djx plan`."""

from __future__ import annotations

import logging
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

from data_juicer_agents.tools.dev.register_custom_operators.logic import (
    register_custom_operators,
)

from .custom_op_scanner import scan_custom_operators
from .generator import ProcessOperatorGenerator


_plan_logger = logging.getLogger(__name__)

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

        # Register custom operators into the DJ registry first, then
        # scan for candidate metadata.  Registration is the single
        # authoritative entry-point; scan_custom_operators only reads
        # the registry to build candidate dicts — no redundant loading.
        registered_op_names: list[str] = []
        if custom_operator_paths:
            _paths = [str(p).strip() for p in custom_operator_paths if str(p).strip()]
            if _paths:
                reg_result = register_custom_operators(paths=_paths)
                if not reg_result.get("ok"):
                    raise ValueError(
                        f"Failed to register custom operators: "
                        f"{reg_result.get('message', 'unknown error')}"
                    )
                if reg_result.get("warnings"):
                    for w in reg_result["warnings"]:
                        _plan_logger.warning("register_custom_operators: %s", w)
                registered_op_names = reg_result.get("registered_operators", [])

        # Inject custom operators into retrieval candidates so the LLM
        # planner can select them alongside built-in operators.
        custom_candidates = scan_custom_operators(registered_op_names or None)
        if custom_candidates:
            existing = retrieval.get("candidates", [])
            existing_names = {c.get("operator_name") for c in existing}
            # Only append custom candidates that are not already present
            # in the retrieval results — no re-ordering of built-in ones.
            appended = [
                c for c in custom_candidates
                if c["operator_name"] not in existing_names
            ]
            if appended:
                merged = existing + appended
                for rank, candidate in enumerate(merged, start=1):
                    candidate["rank"] = rank
                retrieval["candidates"] = merged
                retrieval["candidate_count"] = len(merged)
                retrieval["candidate_names"] = [
                    c["operator_name"] for c in merged
                ]

        # Skip schema probing when using a generated dataset config, since the
        # dataset does not exist yet and cannot be inspected.
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
            custom_operator_paths=custom_operator_paths,
        )
        if not process_result.get("ok"):
            raise ValueError("process spec build failed: " + "; ".join(process_result.get("validation_errors", []) or [str(process_result.get("message", "unknown error"))]))

        system_result = build_system_spec()
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
