# -*- coding: utf-8 -*-
"""Pure logic for plan_save."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from .._shared.schema import PlanModel


def save_plan_file(
    *,
    plan_payload: Dict[str, Any],
    output_path: str,
    overwrite: bool = False,
) -> Dict[str, Any]:
    raw_output = str(output_path or "").strip()
    if not raw_output:
        return {
            "ok": False,
            "error_type": "missing_required",
            "message": "output_path is required for plan_save",
            "requires": ["output_path"],
        }

    try:
        plan = PlanModel.from_dict(plan_payload)
    except Exception as exc:
        return {
            "ok": False,
            "error_type": "plan_invalid_payload",
            "message": f"failed to load plan payload: {exc}",
        }

    out_path = Path(raw_output).expanduser()
    if out_path.exists() and not bool(overwrite):
        return {
            "ok": False,
            "error_type": "file_exists",
            "message": f"output path exists: {out_path}; set overwrite=true to replace",
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(plan.to_dict(), handle, allow_unicode=False, sort_keys=False)

    return {
        "ok": True,
        "plan_path": str(out_path),
        "plan_id": plan.plan_id,
        "modality": plan.modality,
        "operator_names": list(plan.operator_names),
        "warnings": list(plan.warnings),
        "message": f"plan saved: {out_path}",
    }


__all__ = ["save_plan_file"]
