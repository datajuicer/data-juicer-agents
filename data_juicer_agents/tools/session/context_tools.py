# -*- coding: utf-8 -*-
"""Session context and dataset inspection tools."""

from __future__ import annotations

from typing import Any, Dict

from data_juicer_agents.tools.dataset_probe import inspect_dataset_schema

from .runtime import SessionToolRuntime, to_int, to_string_list


def get_session_context(runtime: SessionToolRuntime) -> Dict[str, Any]:
    runtime.debug("tool:get_session_context")
    payload = runtime.context_payload()
    payload["ok"] = True
    return payload


def set_session_context(
    runtime: SessionToolRuntime,
    *,
    dataset_path: str = "",
    export_path: str = "",
    plan_path: str = "",
    custom_operator_paths: Any = None,
) -> Dict[str, Any]:
    runtime.debug("tool:set_session_context")
    if str(dataset_path).strip():
        runtime.state.dataset_path = str(dataset_path).strip()
    if str(export_path).strip():
        runtime.state.export_path = str(export_path).strip()
    if str(plan_path).strip():
        runtime.state.plan_path = str(plan_path).strip()
        model = runtime.load_plan_model(runtime.state.plan_path)
        if model is not None:
            runtime.state.draft_plan = model.to_dict()
            runtime.state.draft_plan_path_hint = runtime.state.plan_path
            runtime.state.dataset_path = model.dataset_path
            runtime.state.export_path = model.export_path
            runtime.state.custom_operator_paths = list(model.custom_operator_paths)

    paths = to_string_list(custom_operator_paths)
    if paths:
        runtime.state.custom_operator_paths = paths

    return {
        "ok": True,
        "message": "session context updated",
        "context": runtime.context_payload(),
    }


def inspect_dataset(
    runtime: SessionToolRuntime,
    *,
    dataset_path: str = "",
    sample_size: int = 20,
) -> Dict[str, Any]:
    runtime.debug(
        f"tool:inspect_dataset dataset_path={dataset_path or runtime.state.dataset_path} sample_size={sample_size}"
    )
    resolved_dataset = str(dataset_path).strip() or (runtime.state.dataset_path or "")
    if not resolved_dataset:
        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["dataset_path"],
            "message": "dataset_path is required for inspect_dataset",
        }

    payload = inspect_dataset_schema(
        dataset_path=resolved_dataset,
        sample_size=max(to_int(sample_size, 20), 1),
    )
    runtime.debug(
        "tool:inspect_dataset result="
        f"ok={payload.get('ok')} modality={payload.get('modality')}"
    )
    if payload.get("ok"):
        runtime.state.dataset_path = resolved_dataset
        runtime.state.last_inspected_dataset = resolved_dataset
        runtime.state.last_dataset_profile = payload
    return payload


__all__ = ["get_session_context", "inspect_dataset", "set_session_context"]
