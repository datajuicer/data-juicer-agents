# -*- coding: utf-8 -*-
"""Pure logic for validate_system_spec."""

from __future__ import annotations

from typing import Any, Dict

from .._shared.schema import SystemSpec
from .._shared.system_spec import validate_system_spec_payload


def validate_system_spec(*, system_spec: Dict[str, Any]) -> Dict[str, Any]:
    spec = SystemSpec.from_dict(system_spec)
    errors, warnings = validate_system_spec_payload(spec)
    return {
        "ok": len(errors) == 0,
        "system_spec": spec.to_dict(),
        "validation_errors": errors,
        "warnings": warnings,
        "message": "system spec is valid" if not errors else "system spec validation failed",
    }


__all__ = ["validate_system_spec", "validate_system_spec_payload"]
