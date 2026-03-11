# -*- coding: utf-8 -*-
"""Single-pass LLM generator for plan draft specs."""

from __future__ import annotations

import json
from typing import Any, Dict

from data_juicer_agents.tools.llm_gateway import call_model_json
from data_juicer_agents.tools.planner import PlanDraftSpec


class PlanDraftGenerator:
    """Generate a plan draft spec from intent and retrieval evidence."""

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
        dataset_path: str,
        export_path: str,
        retrieval_payload: Dict[str, Any],
    ) -> str:
        candidates = retrieval_payload.get("candidates", [])
        dataset_profile = retrieval_payload.get("dataset_profile", {})
        return (
            "You generate a structured draft spec for a deterministic Data-Juicer planner core.\n"
            "Return JSON only with keys: modality, text_keys, image_key, operators, risk_notes, estimation, approval_required.\n"
            "operators must be a non-empty array of objects: {name: string, params: object}.\n"
            "Do not include workflow, revision, template, or markdown.\n"
            "Prefer canonical operator names from retrieved candidates.\n"
            "Use dataset profile hints when available.\n\n"
            f"user_intent: {user_intent}\n"
            f"dataset_path: {dataset_path}\n"
            f"export_path: {export_path}\n"
            f"retrieved_candidates:\n{json.dumps(candidates, ensure_ascii=False, indent=2)}\n"
            f"dataset_profile:\n{json.dumps(dataset_profile, ensure_ascii=False, indent=2)}\n"
        )

    def generate(
        self,
        *,
        user_intent: str,
        dataset_path: str,
        export_path: str,
        retrieval_payload: Dict[str, Any],
    ) -> PlanDraftSpec:
        prompt = self._prompt(
            user_intent=user_intent,
            dataset_path=dataset_path,
            export_path=export_path,
            retrieval_payload=retrieval_payload,
        )
        payload = call_model_json(
            self.model_name,
            prompt,
            api_key=self.api_key,
            base_url=self.base_url,
            thinking=self.thinking,
        )
        if not isinstance(payload, dict):
            raise ValueError("planner draft output must be a JSON object")
        draft = PlanDraftSpec.from_dict(payload)
        if not draft.operators:
            raise ValueError("planner draft output must contain non-empty operators")
        return draft


__all__ = ["PlanDraftGenerator"]
