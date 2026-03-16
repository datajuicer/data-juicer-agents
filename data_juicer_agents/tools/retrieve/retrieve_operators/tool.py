# -*- coding: utf-8 -*-
"""Tool spec for retrieve_operators."""

from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec
from data_juicer_agents.utils.runtime_helpers import to_int

from .input import GenericOutput, RetrieveOperatorsInput
from .logic import extract_candidate_names, retrieve_operator_candidates


def _retrieve_operators(_ctx: ToolContext, args: RetrieveOperatorsInput) -> ToolResult:
    if not args.intent.strip():
        return ToolResult.failure(
            summary="intent is required for retrieve_operators",
            error_type="missing_required",
            data={
                "ok": False,
                "requires": ["intent"],
                "message": "intent is required for retrieve_operators",
            },
        )

    try:
        payload = retrieve_operator_candidates(
            intent=args.intent.strip(),
            top_k=max(to_int(args.top_k, 10), 1),
            mode=(args.mode.strip() or "auto"),
            dataset_path=(args.dataset_path.strip() or None),
        )
    except Exception as exc:
        return ToolResult.failure(
            summary=f"retrieve failed: {exc}",
            error_type="retrieve_failed",
            data={
                "ok": False,
                "error_type": "retrieve_failed",
                "message": f"retrieve failed: {exc}",
            },
        )

    candidate_names = extract_candidate_names(payload)
    result_payload = {
        "ok": True,
        "intent": args.intent.strip(),
        "dataset_path": args.dataset_path.strip(),
        "candidate_count": len(candidate_names),
        "candidate_names": candidate_names,
        "payload": payload,
        "message": "retrieved operator candidates",
    }
    return ToolResult.success(summary="retrieved operator candidates", data=result_payload)


RETRIEVE_OPERATORS = ToolSpec(
    name="retrieve_operators",
    description="Retrieve candidate Data-Juicer operators for a natural-language intent.",
    input_model=RetrieveOperatorsInput,
    output_model=GenericOutput,
    executor=_retrieve_operators,
    tags=("retrieve", "operators"),
    effects="read",
    confirmation="none",
)


__all__ = ["RETRIEVE_OPERATORS"]
