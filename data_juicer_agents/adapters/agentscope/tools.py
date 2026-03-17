# -*- coding: utf-8 -*-
"""AgentScope bindings for tool specifications."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict

from pydantic import ValidationError

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec
from data_juicer_agents.utils.runtime_helpers import to_text_response, truncate_text

from .schema_utils import normalize_tool_schema


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
        return to_text_response(payload)

    _wrapped.__name__ = spec.name
    _wrapped.__doc__ = spec.description
    return _wrapped


__all__ = [
    "build_agentscope_json_schema",
    "build_agentscope_tool_function",
    "default_arg_preview",
    "invoke_tool_spec",
]
