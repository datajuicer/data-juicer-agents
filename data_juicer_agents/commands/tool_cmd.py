# -*- coding: utf-8 -*-
"""Generic `djx tool` command handlers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from pydantic import ValidationError

from data_juicer_agents.core.tool import (
    ToolContext,
    ToolSpec,
    get_active_tool_profile,
    get_tool_spec,
    list_tool_specs,
    tool_is_excluded_from_profile,
)
from data_juicer_agents.core.tool.catalog import ToolGroupImportError
from data_juicer_agents.utils.optional_deps import install_command_for_extras


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


def _resolve_active_profile() -> tuple[str, int] | tuple[Dict[str, Any], int]:
    try:
        profile = get_active_tool_profile()
    except ValueError as exc:
        return (
            _error_payload(
                action="tool",
                message=str(exc),
                error_type="invalid_tool_profile",
            ),
            2,
        )
    return profile, 0


def _install_hint_for_group_import(group_name: str) -> str:
    if group_name in {"apply", "context", "dev", "plan", "process"}:
        return install_command_for_extras("harness")
    return install_command_for_extras("core")


def _group_import_failure_payload(
    *,
    action: str,
    exc: ToolGroupImportError,
    tool_name: str | None = None,
) -> tuple[Dict[str, Any], int]:
    message = (
        f"tool group '{exc.group_name}' requires optional dependencies that are not installed. "
        f"Install them with: {_install_hint_for_group_import(exc.group_name)}"
    )
    if exc.missing_module:
        message += f" Missing module: {exc.missing_module}."
    return (
        _error_payload(
            action=action,
            message=message,
            error_type="missing_optional_dependency",
            tool_name=tool_name,
            group=exc.group_name,
            missing_module=exc.missing_module,
        ),
        2,
    )


def _profile_unavailable_payload(*, action: str, tool_name: str, profile: str) -> tuple[Dict[str, Any], int]:
    message = (
        f"tool '{tool_name}' is not available in the '{profile}' tool profile. "
        f"Install {install_command_for_extras('core')} and unset DJX_TOOL_PROFILE "
        "to access the full tool catalog."
    )
    return (
        _error_payload(
            action=action,
            message=message,
            error_type="tool_not_available_in_profile",
            tool_name=tool_name,
            profile=profile,
        ),
        2,
    )


def _resolve_tool_spec(
    *,
    action: str,
    tool_name: str,
    profile: str,
) -> tuple[ToolSpec | None, tuple[Dict[str, Any], int] | None]:
    try:
        spec = get_tool_spec(tool_name, profile=profile)
    except ToolGroupImportError as exc:
        return None, _group_import_failure_payload(
            action=action,
            exc=exc,
            tool_name=tool_name,
        )
    except KeyError:
        if tool_is_excluded_from_profile(tool_name, profile):
            return None, _profile_unavailable_payload(
                action=action,
                tool_name=tool_name,
                profile=profile,
            )
        try:
            _ = get_tool_spec(tool_name)
        except KeyError:
            pass
        except ToolGroupImportError as exc:
            return None, _group_import_failure_payload(
                action=action,
                exc=exc,
                tool_name=tool_name,
            )
        else:
            if profile != "default":
                return None, _profile_unavailable_payload(
                    action=action,
                    tool_name=tool_name,
                    profile=profile,
                )
        return None, (
            _error_payload(
                action=action,
                message=f"unknown tool: {tool_name}",
                error_type="tool_not_found",
                tool_name=tool_name,
                profile=profile,
            ),
            2,
        )
    return spec, None


def _execute_list(args: Any) -> tuple[Dict[str, Any], int]:
    resolved = _resolve_active_profile()
    if isinstance(resolved[0], dict):
        return resolved  # type: ignore[return-value]
    profile = resolved[0]
    tags = list(getattr(args, "tag", []) or [])
    try:
        specs = list_tool_specs(tags=tags, profile=profile)
    except ToolGroupImportError as exc:
        return _group_import_failure_payload(action="tool_list", exc=exc)
    payload = _success_payload(
        action="tool_list",
        count=len(specs),
        filter_tags=tags,
        profile=profile,
        tools=[_tool_metadata(spec) for spec in specs],
    )
    return payload, 0


def _execute_schema(args: Any) -> tuple[Dict[str, Any], int]:
    resolved = _resolve_active_profile()
    if isinstance(resolved[0], dict):
        return resolved  # type: ignore[return-value]
    profile = resolved[0]
    tool_name = str(getattr(args, "tool_name", "") or "").strip()
    spec, error = _resolve_tool_spec(
        action="tool_schema",
        tool_name=tool_name,
        profile=profile,
    )
    if error is not None:
        return error
    assert spec is not None

    payload = _success_payload(
        action="tool_schema",
        profile=profile,
        tool=_tool_metadata(spec),
        input_schema=spec.input_model.model_json_schema(),
    )
    return payload, 0


def _execute_run(args: Any) -> tuple[Dict[str, Any], int]:
    resolved = _resolve_active_profile()
    if isinstance(resolved[0], dict):
        return resolved  # type: ignore[return-value]
    profile = resolved[0]
    tool_name = str(getattr(args, "tool_name", "") or "").strip()
    spec, error = _resolve_tool_spec(
        action="tool_run",
        tool_name=tool_name,
        profile=profile,
    )
    if error is not None:
        return error
    assert spec is not None

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
                profile=profile,
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
                profile=profile,
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
                profile=profile,
            ),
            2,
        )

    payload = result.to_payload(action=spec.name)
    payload.setdefault("profile", profile)
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
