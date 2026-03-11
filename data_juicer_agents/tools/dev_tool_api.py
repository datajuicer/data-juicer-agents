# -*- coding: utf-8 -*-
"""Tool-level APIs for custom operator scaffold generation."""

from __future__ import annotations

from typing import Any, Dict

from data_juicer_agents.tools.dev_scaffold import (
    ScaffoldResult,
    generate_operator_scaffold,
    run_smoke_check,
)


class DevUseCase:
    """Generate and optionally smoke-check custom operator scaffolds."""

    @staticmethod
    def execute(
        *,
        intent: str,
        operator_name: str,
        output_dir: str,
        operator_type: str | None = None,
        from_retrieve: str | None = None,
        smoke_check: bool = False,
    ) -> Dict[str, Any]:
        missing = [
            field
            for field, value in {
                "intent": intent,
                "operator_name": operator_name,
                "output_dir": output_dir,
            }.items()
            if not str(value).strip()
        ]
        if missing:
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": missing,
                "message": "intent/operator_name/output_dir are required",
            }

        try:
            scaffold = generate_operator_scaffold(
                intent=str(intent).strip(),
                operator_name=str(operator_name).strip(),
                output_dir=str(output_dir).strip(),
                operator_type=(str(operator_type).strip() or None) if operator_type is not None else None,
                from_retrieve_path=(str(from_retrieve).strip() or None) if from_retrieve is not None else None,
            )
        except Exception as exc:
            return {
                "ok": False,
                "error_type": "dev_failed",
                "message": f"dev scaffold generation failed: {exc}",
            }

        return DevUseCase._serialize_result(scaffold=scaffold, smoke_check=bool(smoke_check))

    @staticmethod
    def _serialize_result(scaffold: ScaffoldResult, smoke_check: bool) -> Dict[str, Any]:
        smoke: Dict[str, Any] | None = None
        if smoke_check:
            smoke_ok, smoke_message = run_smoke_check(scaffold)
            smoke = {
                "ok": bool(smoke_ok),
                "message": str(smoke_message),
            }

        result: Dict[str, Any] = {
            "ok": True if smoke is None else bool(smoke.get("ok")),
            "operator_name": scaffold.operator_name,
            "operator_type": scaffold.operator_type,
            "class_name": scaffold.class_name,
            "output_dir": str(scaffold.output_dir),
            "generated_files": list(scaffold.generated_files),
            "summary_path": str(scaffold.summary_path),
            "notes": list(scaffold.notes),
        }
        if smoke is not None:
            result["smoke_check"] = smoke
        return result


__all__ = ["DevUseCase"]
