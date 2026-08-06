# -*- coding: utf-8 -*-
"""AgentScope bindings for tool specifications."""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict

from pydantic import ValidationError

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec
from data_juicer_agents.utils.runtime_helpers import (
    to_bool,
    to_text_response,
    truncate_text,
)

from .schema_utils import normalize_tool_schema

_MODEL_TEXT_LIMIT = 2400
_MODEL_LIST_LIMIT = 12
_MODEL_OPERATOR_LIMIT = 10
_MODEL_PARAM_LIMIT = 20


def tool_result_compaction_enabled() -> bool:
    return to_bool(os.environ.get("DJA_TOOL_RESULT_COMPACTION_ENABLED"), True)


def build_agentscope_json_schema(spec: ToolSpec) -> Dict[str, Any]:
    parameters = normalize_tool_schema(spec.input_model.model_json_schema())
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": parameters,
        },
    }


def _preview_value(value: Any, *, limit: int = 800) -> Any:
    if isinstance(value, str):
        return truncate_text(value, limit=limit)
    if isinstance(value, (dict, list)):
        try:
            return truncate_text(json.dumps(value, ensure_ascii=False), limit=limit)
        except Exception:
            return truncate_text(str(value), limit=limit)
    return value


def default_arg_preview(_spec: ToolSpec, raw_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _preview_value(value) for key, value in raw_kwargs.items()}


def _short_text(value: Any, *, limit: int = _MODEL_TEXT_LIMIT) -> str:
    return truncate_text(str(value or ""), limit=limit).strip()


def _compact_list(items: Any, *, limit: int = _MODEL_LIST_LIMIT) -> list[Any]:
    return list(items[:limit]) if isinstance(items, list) else []


def _compact_mapping(value: Any, *, text_limit: int = 400) -> Any:
    if isinstance(value, str):
        return _short_text(value, limit=text_limit)
    if isinstance(value, list):
        return [
            _compact_mapping(item, text_limit=text_limit)
            for item in value[:_MODEL_LIST_LIMIT]
        ]
    if isinstance(value, dict):
        return {
            str(key): _compact_mapping(item, text_limit=text_limit)
            for key, item in value.items()
        }
    return value


def _compact_operator(item: Any, *, include_parameters: bool = False) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {"value": _short_text(item, limit=300)}
    compact = {
        key: item.get(key)
        for key in (
            "operator_name",
            "resolved_name",
            "operator_type",
            "score",
            "source",
            "source_path",
            "test_path",
        )
        if item.get(key) not in (None, "")
    }
    if item.get("tags"):
        compact["tags"] = _compact_list(item.get("tags"), limit=8)
    if item.get("description"):
        compact["description"] = _short_text(item.get("description"), limit=360)
    if include_parameters and isinstance(item.get("parameters"), list):
        compact["parameters"] = [
            _compact_mapping(param, text_limit=260)
            for param in item["parameters"][:_MODEL_PARAM_LIMIT]
            if isinstance(param, dict)
        ]
    return compact


def _base_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    base: Dict[str, Any] = {}
    for key in ("ok", "action", "message", "error_type"):
        if key in payload:
            base[key] = payload[key]
    for key in ("warnings", "validation_errors", "requires"):
        if isinstance(payload.get(key), list):
            base[key] = _compact_list(payload.get(key), limit=8)
    return base


def _recipe_summary(recipe: Any) -> Dict[str, Any]:
    if not isinstance(recipe, dict):
        return {}
    process = recipe.get("process", [])
    operators = []
    if isinstance(process, list):
        for step in process[:_MODEL_OPERATOR_LIMIT]:
            if isinstance(step, dict) and step:
                operators.extend(str(name) for name in step.keys())
    return {
        "dataset_path": recipe.get("dataset_path"),
        "export_path": recipe.get("export_path"),
        "text_keys": recipe.get("text_keys"),
        "image_key": recipe.get("image_key"),
        "audio_key": recipe.get("audio_key"),
        "video_key": recipe.get("video_key"),
        "operator_names": operators,
        "np": recipe.get("np"),
        "executor_type": recipe.get("executor_type"),
    }


def compact_payload_for_model(
    tool_name: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Return a semantically faithful, smaller payload for ReAct memory.

    The full payload is still passed through runtime events; this function only
    controls what is written into AgentScope tool_result memory.
    """
    if not isinstance(payload, dict):
        return {"ok": True, "result": _compact_mapping(payload)}

    if payload.get("ok") is False:
        compact = _base_payload(payload)
        for key in ("error", "error_message", "stderr", "stdout"):
            if payload.get(key):
                compact[key] = _short_text(payload.get(key), limit=1200)
        return compact

    compact = _base_payload(payload)

    if tool_name == "inspect_dataset":
        for key in (
            "dataset",
            "inspected_path",
            "sampled_records",
            "scanned_lines",
            "modality",
            "keys",
            "candidate_text_keys",
            "candidate_image_keys",
        ):
            if key in payload:
                compact[key] = _compact_mapping(payload[key], text_limit=300)
        if isinstance(payload.get("key_stats"), dict):
            compact["key_stats"] = {
                str(key): _compact_mapping(value, text_limit=180)
                for key, value in payload["key_stats"].items()
            }
        if isinstance(payload.get("sample_preview"), list):
            compact["sample_preview"] = [
                _compact_mapping(item, text_limit=180)
                for item in payload["sample_preview"][:2]
            ]
        return compact

    if tool_name in {"retrieve_operators", "retrieve_operators_api"}:
        for key in ("intent", "mode", "source", "candidate_names", "requested_tags"):
            if key in payload:
                compact[key] = _compact_mapping(payload[key], text_limit=240)
        if isinstance(payload.get("candidates"), list):
            compact["candidates"] = [
                _compact_operator(item)
                for item in payload["candidates"][:_MODEL_OPERATOR_LIMIT]
            ]
            compact["candidate_count"] = len(payload["candidates"])
        return compact

    if tool_name == "list_operator_catalog":
        for key in (
            "total_count",
            "returned_count",
            "op_type_filter",
            "requested_tags",
            "include_parameters",
            "limit",
        ):
            if key in payload:
                compact[key] = payload[key]
        if isinstance(payload.get("operators"), list):
            include_parameters = bool(payload.get("include_parameters"))
            compact["operators"] = [
                _compact_operator(item, include_parameters=include_parameters)
                for item in payload["operators"][:_MODEL_OPERATOR_LIMIT]
            ]
            compact["compacted_count"] = len(compact["operators"])
        return compact

    if tool_name == "get_operator_info":
        for key in (
            "requested_name",
            "resolved_name",
            "resolved",
            "exact_match",
            "operator_type",
            "tags",
            "source_path",
            "test_path",
        ):
            if key in payload:
                compact[key] = _compact_mapping(payload[key], text_limit=260)
        if payload.get("description"):
            compact["description"] = _short_text(payload.get("description"), limit=500)
        if isinstance(payload.get("parameters"), list):
            compact["parameters"] = [
                _compact_mapping(param, text_limit=300)
                for param in payload["parameters"][:_MODEL_PARAM_LIMIT]
            ]
        return compact

    if tool_name == "assemble_plan" and isinstance(payload.get("plan"), dict):
        # Keep the exact plan for follow-up plan_validate / plan_save calls.
        compact.update(
            {
                "plan": payload["plan"],
                "plan_id": payload.get("plan_id"),
                "operator_names": payload.get("operator_names"),
                "modality": payload.get("modality"),
                "plan_summary": _recipe_summary(payload["plan"].get("recipe")),
            }
        )
        return compact

    if tool_name in {"execute_bash", "execute_python_code"}:
        for key in ("returncode", "timeout_sec", "command", "message"):
            if key in payload:
                compact[key] = payload[key]
        for key in ("stdout", "stderr"):
            if payload.get(key):
                compact[key] = _short_text(payload.get(key), limit=1800)
        return compact

    if tool_name == "view_text_file":
        for key, value in payload.items():
            if key in {"content", "text"}:
                compact[key] = _short_text(value, limit=1800)
            else:
                compact[key] = value
        return compact

    return _compact_mapping(payload, text_limit=800)


def invoke_tool_spec(
    spec: ToolSpec,
    *,
    ctx: ToolContext,
    raw_kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        result = spec.execute(ctx, raw_kwargs)
    except ValidationError as exc:
        return {
            "ok": False,
            "error_type": "invalid_arguments",
            "message": f"invalid arguments for {spec.name}: {exc}",
            "validation_errors": json.loads(exc.json()),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error_type": "tool_exception",
            "message": f"{spec.name} failed: {exc}",
        }

    if isinstance(result, ToolResult):
        return result.to_payload(action=spec.name)
    if isinstance(result, dict):
        return result
    return {
        "ok": False,
        "error_type": "invalid_tool_result",
        "message": f"{spec.name} returned unsupported result type: {type(result)}",
    }


def build_agentscope_tool_function(
    spec: ToolSpec,
    *,
    ctx_factory: Callable[[], ToolContext],
    runtime_invoke: Callable[[str, Dict[str, Any], Callable[[], Dict[str, Any]]], Dict[str, Any]],
    arg_preview: Callable[[ToolSpec, Dict[str, Any]], Dict[str, Any]] | None = None,
):
    previewer = arg_preview or default_arg_preview

    def _wrapped(**kwargs: Any):
        payload = runtime_invoke(
            spec.name,
            previewer(spec, kwargs),
            lambda: invoke_tool_spec(spec, ctx=ctx_factory(), raw_kwargs=kwargs),
        )
        if tool_result_compaction_enabled():
            model_payload = compact_payload_for_model(spec.name, payload)
        else:
            model_payload = payload
        return to_text_response(model_payload)

    _wrapped.__name__ = spec.name
    _wrapped.__doc__ = spec.description
    return _wrapped


__all__ = [
    "build_agentscope_json_schema",
    "build_agentscope_tool_function",
    "compact_payload_for_model",
    "default_arg_preview",
    "invoke_tool_spec",
    "tool_result_compaction_enabled",
]
