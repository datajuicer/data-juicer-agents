# -*- coding: utf-8 -*-
"""Generic `djx tool` command handlers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from pydantic import ValidationError

from data_juicer_agents.core.tool import ToolContext, ToolSpec, get_tool_spec, list_tool_specs


def _tool_metadata(spec: ToolSpec) -> Dict[str, Any]:
    return {
        "name": spec.name,
        "description": spec.description,
        "tags": list(spec.tags),
        "effects": spec.effects,
        "confirmation": spec.confirmation,
        "input_model": spec.input_model.__name__,
        "output_model": spec.output_model.__name__ if spec.output_model is not None else None,
    }


def _success_payload(*, action: str, **data: Any) -> Dict[str, Any]:
    payload = {"ok": True, "action": action}
    payload.update(data)
    return payload


def _error_payload(
    *,
    action: str,
    message: str,
    error_type: str,
    tool_name: str | None = None,
    **data: Any,
) -> Dict[str, Any]:
    payload = {
        "ok": False,
        "action": action,
        "error_type": error_type,
        "message": str(message),
    }
    if tool_name:
        payload["tool_name"] = tool_name
    payload.update(data)
    return payload


def _emit_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _load_input_payload(args: Any) -> Dict[str, Any]:
    raw_json = getattr(args, "input_json", None)
    input_file = getattr(args, "input_file", None)
    if raw_json is not None:
        source = str(raw_json)
    else:
        source = Path(str(input_file)).expanduser().read_text(encoding="utf-8")

    try:
        payload = json.loads(source)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON input: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("tool input must decode to a JSON object")
    return payload


def _build_tool_context(working_dir: str | None) -> ToolContext:
    raw = str(working_dir or "").strip() or "./.djx"
    resolved = str(Path(raw).expanduser())
    return ToolContext(working_dir=resolved, artifacts_dir=resolved)


def _execute_list(args: Any) -> tuple[Dict[str, Any], int]:
    tags = list(getattr(args, "tag", []) or [])
    specs = list_tool_specs(tags=tags)
    payload = _success_payload(
        action="tool_list",
        count=len(specs),
        filter_tags=tags,
        tools=[_tool_metadata(spec) for spec in specs],
    )
    return payload, 0


def _execute_schema(args: Any) -> tuple[Dict[str, Any], int]:
    tool_name = str(getattr(args, "tool_name", "") or "").strip()
    try:
        spec = get_tool_spec(tool_name)
    except KeyError:
        return (
            _error_payload(
                action="tool_schema",
                message=f"unknown tool: {tool_name}",
                error_type="tool_not_found",
                tool_name=tool_name,
            ),
            2,
        )

    payload = _success_payload(
        action="tool_schema",
        tool=_tool_metadata(spec),
        input_schema=spec.input_model.model_json_schema(),
    )
    return payload, 0


def _execute_run(args: Any) -> tuple[Dict[str, Any], int]:
    tool_name = str(getattr(args, "tool_name", "") or "").strip()
    try:
        spec = get_tool_spec(tool_name)
    except KeyError:
        return (
            _error_payload(
                action="tool_run",
                message=f"unknown tool: {tool_name}",
                error_type="tool_not_found",
                tool_name=tool_name,
            ),
            2,
        )

    if spec.confirmation != "none" and not bool(getattr(args, "yes", False)):
        return (
            _error_payload(
                action=spec.name,
                message=(
                    f"tool '{spec.name}' requires explicit confirmation; "
                    "re-run with --yes to proceed"
                ),
                error_type="confirmation_required",
                tool_name=spec.name,
                confirmation=spec.confirmation,
                effects=spec.effects,
            ),
            3,
        )

    try:
        raw_input = _load_input_payload(args)
    except (OSError, ValueError) as exc:
        return (
            _error_payload(
                action=spec.name,
                message=str(exc),
                error_type="invalid_input",
                tool_name=spec.name,
            ),
            2,
        )

    ctx = _build_tool_context(getattr(args, "working_dir", None))
    try:
        result = spec.execute(ctx, raw_input)
    except ValidationError as exc:
        return (
            _error_payload(
                action=spec.name,
                message="tool input validation failed",
                error_type="input_validation_failed",
                tool_name=spec.name,
                validation_errors=exc.errors(),
            ),
            2,
        )

    payload = result.to_payload(action=spec.name)
    payload.setdefault("tool_name", spec.name)
    payload.setdefault("effects", spec.effects)
    payload.setdefault("confirmation", spec.confirmation)
    payload.setdefault("tags", list(spec.tags))
    return payload, (0 if result.ok else 4)


def run_tool(args: Any) -> int:
    action = str(getattr(args, "tool_action", "") or "").strip()
    if action == "list":
        payload, code = _execute_list(args)
    elif action == "schema":
        payload, code = _execute_schema(args)
    elif action == "run":
        payload, code = _execute_run(args)
    else:
        payload = _error_payload(
            action="tool",
            message=f"unsupported tool action: {action}",
            error_type="unsupported_action",
        )
        code = 2

    _emit_json(payload)
    return int(code)


__all__ = ["run_tool"]
