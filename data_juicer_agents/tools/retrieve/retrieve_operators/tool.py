# -*- coding: utf-8 -*-
"""Tool spec for retrieve_operators."""

from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec
from data_juicer_agents.utils.runtime_helpers import to_int

from .input import GenericOutput, RetrieveOperatorsInput
from .logic import retrieve_operator_candidates_local


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

    parsed_tags = [t.strip() for t in (args.tags or []) if t.strip()] or None

    try:
        payload = retrieve_operator_candidates_local(
            intent=args.intent.strip(),
            top_k=max(to_int(args.top_k, 10), 1),
            mode=(args.mode.strip() or "auto"),
            op_type=(args.op_type.strip() or None),
            tags=parsed_tags,
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

    return ToolResult.success(summary="retrieved operator candidates", data=payload)


RETRIEVE_OPERATORS = ToolSpec(
    name="retrieve_operators",
    description=(
        "Retrieve candidate Data-Juicer operators using local retrieval. "
        "Supports natural-language search (auto, bm25) and regex matching on operator names (regex)."
    ),
    input_model=RetrieveOperatorsInput,
    output_model=GenericOutput,
    executor=_retrieve_operators,
    tags=("retrieve", "operators"),
    effects="read",
    confirmation="none",
)


__all__ = ["RETRIEVE_OPERATORS"]
