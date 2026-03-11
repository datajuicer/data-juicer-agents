# -*- coding: utf-8 -*-
"""Session custom-operator development tools."""

from __future__ import annotations

from typing import Any, Dict

from data_juicer_agents.tools.dev_tool_api import DevUseCase

from .runtime import SessionToolRuntime, to_bool


def develop_operator(
    runtime: SessionToolRuntime,
    *,
    intent: str,
    operator_name: str = "",
    output_dir: str = "",
    operator_type: str = "",
    from_retrieve: str = "",
    smoke_check: bool = False,
) -> Dict[str, Any]:
    runtime.debug(
        "tool:develop_operator "
        f"intent={intent!r} operator_name={operator_name!r} output_dir={output_dir!r} "
        f"operator_type={operator_type!r} smoke_check={smoke_check}"
    )
    result = DevUseCase.execute(
        intent=str(intent).strip(),
        operator_name=str(operator_name).strip(),
        output_dir=str(output_dir).strip(),
        operator_type=(str(operator_type).strip() or None),
        from_retrieve=(str(from_retrieve).strip() or None),
        smoke_check=to_bool(smoke_check, False),
    )
    if not result.get("ok"):
        runtime.debug(f"tool:develop_operator failed error={result.get('message')}")
        return {
            "ok": False,
            "error_type": str(result.get("error_type", "dev_failed")),
            "requires": list(result.get("requires", [])),
            "message": str(result.get("message", "dev scaffold generation failed")),
        }

    path_str = str(result.get("output_dir", "")).strip()
    if path_str and path_str not in runtime.state.custom_operator_paths:
        runtime.state.custom_operator_paths.append(path_str)

    payload: Dict[str, Any] = {
        "ok": bool(result.get("ok")),
        "action": "dev",
        "operator_name": str(result.get("operator_name", "")),
        "operator_type": str(result.get("operator_type", "")),
        "class_name": str(result.get("class_name", "")),
        "output_dir": path_str,
        "generated_files": list(result.get("generated_files", [])),
        "summary_path": str(result.get("summary_path", "")),
        "notes": list(result.get("notes", [])),
        "context": runtime.context_payload(),
    }
    if result.get("smoke_check") is not None:
        payload["smoke_check"] = result.get("smoke_check")
    runtime.debug(
        f"tool:develop_operator result operator_name={payload.get('operator_name')} output_dir={payload.get('output_dir')}"
    )
    return payload


__all__ = ["develop_operator"]
