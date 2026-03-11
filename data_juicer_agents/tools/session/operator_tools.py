# -*- coding: utf-8 -*-
"""Session retrieval-oriented tools."""

from __future__ import annotations

from typing import Any, Dict

from data_juicer_agents.tools.op_manager.retrieval_service import (
    extract_candidate_names,
    retrieve_operator_candidates,
)

from .runtime import SessionToolRuntime, to_int


def retrieve_operators(
    runtime: SessionToolRuntime,
    *,
    intent: str,
    top_k: int = 10,
    mode: str = "auto",
    dataset_path: str = "",
) -> Dict[str, Any]:
    runtime.debug(
        f"tool:retrieve_operators intent={intent!r} top_k={top_k} mode={mode} dataset_path={dataset_path or runtime.state.dataset_path}"
    )
    if not str(intent).strip():
        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["intent"],
            "message": "intent is required for retrieve_operators",
        }

    resolved_dataset = str(dataset_path).strip() or (runtime.state.dataset_path or "")
    try:
        payload = retrieve_operator_candidates(
            intent=str(intent).strip(),
            top_k=max(to_int(top_k, 10), 1),
            mode=str(mode or "auto").strip() or "auto",
            dataset_path=(resolved_dataset or None),
        )
    except Exception as exc:
        runtime.debug(f"tool:retrieve_operators failed error={exc}")
        return {
            "ok": False,
            "error_type": "retrieve_failed",
            "message": f"retrieve failed: {exc}",
        }
    candidate_names = extract_candidate_names(payload)
    if resolved_dataset:
        runtime.state.dataset_path = resolved_dataset
    runtime.state.last_retrieval = {
        "intent": str(intent).strip(),
        "dataset_path": str(resolved_dataset or ""),
        "candidate_names": candidate_names,
        "payload": payload,
    }
    runtime.debug(
        "tool:retrieve_operators result="
        f"candidate_count={payload.get('candidate_count')} source={payload.get('retrieval_source')}"
    )
    return {
        "ok": True,
        "action": "retrieve_operators",
        "intent": str(intent).strip(),
        "dataset_path": resolved_dataset,
        "candidate_count": len(candidate_names),
        "candidate_names": candidate_names,
        "payload": payload,
        "message": "retrieved operator candidates",
    }


__all__ = ["retrieve_operators"]
