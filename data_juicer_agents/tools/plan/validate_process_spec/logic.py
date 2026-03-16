# -*- coding: utf-8 -*-
"""Pure logic for validate_process_spec."""

from __future__ import annotations

from typing import Any, Dict

from .._shared.schema import ProcessSpec
from .._shared.process_spec import validate_process_spec_payload


def validate_process_spec(*, process_spec: Dict[str, Any]) -> Dict[str, Any]:
    spec = ProcessSpec.from_dict(process_spec)
    errors, warnings = validate_process_spec_payload(spec)
    return {
        "ok": len(errors) == 0,
        "process_spec": spec.to_dict(),
        "validation_errors": errors,
        "warnings": warnings,
        "operator_names": [item.name for item in spec.operators],
        "message": "process spec is valid" if not errors else "process spec validation failed",
    }


__all__ = ["validate_process_spec", "validate_process_spec_payload"]
