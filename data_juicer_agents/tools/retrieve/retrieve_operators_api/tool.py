# -*- coding: utf-8 -*-
"""Tool spec for retrieve_operators_api."""

from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec
from data_juicer_agents.utils.runtime_helpers import to_int

from .input import GenericOutput, RetrieveOperatorsAPIInput
from .logic import retrieve_operator_candidates_api


def _api_retrieval_is_unavailable(payload: dict) -> bool:
    trace = payload.get("retrieval_trace")
    if not isinstance(trace, list) or not trace:
        return False
    if payload.get("retrieval_source") or payload.get("candidate_count"):
        return False
    return all(
        isinstance(item, dict)
        and str(item.get("reason", "")).strip() == "missing_api_key"
        and str(item.get("status", "")).strip() in {"failed", "skipped"}
        for item in trace
    )


def _retrieve_operators_api(_ctx: ToolContext, args: RetrieveOperatorsAPIInput) -> ToolResult:
    if not args.intent.strip():
        return ToolResult.failure(
            summary="intent is required for retrieve_operators_api",
            error_type="missing_required",
            data={
                "ok": False,
                "requires": ["intent"],
                "message": "intent is required for retrieve_operators_api",
            },
        )

    parsed_tags = [t.strip() for t in (args.tags or []) if t.strip()] or None

    try:
        payload = retrieve_operator_candidates_api(
            intent=args.intent.strip(),
            top_k=max(to_int(args.top_k, 10), 1),
            mode=(args.mode.strip() or "auto"),
            op_type=(args.op_type.strip() or None),
            tags=parsed_tags,
            dataset_source=args.dataset_source,
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

    if _api_retrieval_is_unavailable(payload):
        message = "API retrieval unavailable: missing API key for llm/vector backends"
        failure_payload = dict(payload)
        failure_payload.update(
            {
                "ok": False,
                "error_type": "missing_api_key",
                "message": message,
            }
        )
        return ToolResult.failure(
            summary=message,
            error_type="missing_api_key",
            data=failure_payload,
        )

    return ToolResult.success(summary="retrieved operator candidates via api", data=payload)


RETRIEVE_OPERATORS_API = ToolSpec(
    name="retrieve_operators_api",
    description=(
        "Retrieve candidate Data-Juicer operators using API-backed semantic retrieval. "
        "Supports semantic LLM ranking (llm) and vector similarity retrieval (vector)."
    ),
    input_model=RetrieveOperatorsAPIInput,
    output_model=GenericOutput,
    executor=_retrieve_operators_api,
    tags=("retrieve", "operators"),
    effects="read",
    confirmation="none",
)


__all__ = ["RETRIEVE_OPERATORS_API"]
