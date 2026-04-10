# -*- coding: utf-8 -*-
"""Pure logic for build_process_spec."""

from __future__ import annotations

from typing import Any, Dict, Iterable

from .._shared.normalize import normalize_string_list
from .._shared.schema import ProcessSpec
from .._shared.process_spec import validate_process_spec_payload

def build_process_spec(
    *,
    operators: Iterable[Any] | None,
    custom_operator_paths: Iterable[Any] | None = None,
) -> Dict[str, Any]:
    if operators is None:
        return {
            "ok": False,
            "error_type": "missing_required",
            "message": "operators is required for build_process_spec",
            "requires": ["operators"],
        }
    normalized_paths = normalize_string_list(custom_operator_paths)
    spec = ProcessSpec.from_dict({
        "operators": list(operators),
        "custom_operator_paths": normalized_paths,
    })
    errors, warnings = validate_process_spec_payload(
        spec, custom_operator_paths=normalized_paths or None,
    )
    return {
        "ok": len(errors) == 0,
        "process_spec": spec.to_dict(),
        "validation_errors": errors,
        "warnings": warnings,
        "operator_names": [item.name for item in spec.operators],
        "message": "process spec built" if not errors else "process spec build failed",
    }

__all__ = ["build_process_spec"]
