# -*- coding: utf-8 -*-
"""LLM generator for process operator lists used by CLI plan orchestration."""

from __future__ import annotations

import json
from typing import Any, Dict

from data_juicer_agents.utils.llm_gateway import call_model_json


class ProcessOperatorGenerator:
    """Generate an operator list for staged plan assembly."""

    def __init__(
        self,
        *,
        model_name: str,
        api_key: str | None = None,
        base_url: str | None = None,
        thinking: bool | None = None,
    ):
        self.model_name = str(model_name or "").strip()
        self.api_key = str(api_key or "").strip() or None
        self.base_url = str(base_url or "").strip() or None
        self.thinking = thinking

    @staticmethod
    def _prompt(
        *,
        user_intent: str,
        retrieval_payload: Dict[str, Any],
        dataset_spec: Dict[str, Any],
        dataset_profile: Dict[str, Any] | None = None,
    ) -> str:
        candidates = retrieval_payload.get("candidates", [])
        profile_payload = dataset_profile if isinstance(dataset_profile, dict) else {}
        dataset_binding = {}
        if isinstance(dataset_spec, dict):
            binding = dataset_spec.get("binding", {})
            if isinstance(binding, dict):
                dataset_binding = binding
        custom_candidates = [c for c in candidates if c.get("is_custom")]
        builtin_candidates = [c for c in candidates if not c.get("is_custom")]

        prompt_parts = [
            "You generate only the operator list for a staged deterministic Data-Juicer planner.\n"
            "Return JSON only with one key: operators.\n"
            "operators must be a non-empty array of objects: {name: string, params: object}.\n"
            "Use canonical operator names from retrieved candidates.\n"
            "Fill concrete params whenever a threshold, mode, or explicit option is already known.\n"
            "Do not include modality, text_keys, image_key, risk_notes, estimation, approval_required, workflow, or markdown.\n",
        ]

        if custom_candidates:
            prompt_parts.append(
                "\nThe user has provided custom operators via --custom-operator-paths. "
                "These operators are specifically designed for this task and should be preferred "
                "when they match the user intent. Include them in the operator list.\n"
                f"\ncustom_operators:\n{json.dumps(custom_candidates, ensure_ascii=False, indent=2)}\n"
            )

        prompt_parts.append(
            f"\nuser_intent: {user_intent}\n"
            f"dataset_binding:\n{json.dumps(dataset_binding, ensure_ascii=False, indent=2)}\n"
            f"retrieved_candidates:\n{json.dumps(builtin_candidates, ensure_ascii=False, indent=2)}\n"
            f"dataset_profile:\n{json.dumps(profile_payload, ensure_ascii=False, indent=2)}\n"
        )

        return "\n".join(prompt_parts)

    def generate(
        self,
        *,
        user_intent: str,
        retrieval_payload: Dict[str, Any],
        dataset_spec: Dict[str, Any],
        dataset_profile: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        prompt = self._prompt(
            user_intent=user_intent,
            retrieval_payload=retrieval_payload,
            dataset_spec=dataset_spec,
            dataset_profile=dataset_profile,
        )
        payload = call_model_json(
            self.model_name,
            prompt,
            api_key=self.api_key,
            base_url=self.base_url,
            thinking=self.thinking,
        )
        if not isinstance(payload, dict):
            raise ValueError("planner operator output must be a JSON object")
        operators = payload.get("operators", [])
        if not isinstance(operators, list) or not operators:
            raise ValueError("planner operator output must contain non-empty operators")
        return {"operators": operators}


__all__ = ["ProcessOperatorGenerator"]
