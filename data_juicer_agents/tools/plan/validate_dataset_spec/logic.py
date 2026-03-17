# -*- coding: utf-8 -*-
"""Pure logic for validate_dataset_spec."""

from __future__ import annotations

from typing import Any, Dict

from .._shared.schema import DatasetSpec
from .._shared.dataset_spec import validate_dataset_spec_payload


def validate_dataset_spec(*, dataset_spec: Dict[str, Any], dataset_profile: Dict[str, Any] | None = None) -> Dict[str, Any]:
    spec = DatasetSpec.from_dict(dataset_spec)
    errors, warnings = validate_dataset_spec_payload(spec, dataset_profile=dataset_profile)
    return {
        "ok": len(errors) == 0,
        "dataset_spec": spec.to_dict(),
        "validation_errors": errors,
        "warnings": warnings,
        "message": "dataset spec is valid" if not errors else "dataset spec validation failed",
    }


__all__ = ["validate_dataset_spec", "validate_dataset_spec_payload"]
