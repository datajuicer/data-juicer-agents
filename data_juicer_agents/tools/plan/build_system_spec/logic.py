# -*- coding: utf-8 -*-
"""Pure logic for build_system_spec."""

from __future__ import annotations

from typing import Any, Dict, Iterable

from .._shared.schema import SystemSpec
from .._shared.system_spec import SYSTEM_SPEC_DEFERRED_WARNING, validate_system_spec_payload


def _normalize_string_list(values: Iterable[Any] | None) -> list[str]:
    items: list[str] = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        items.append(text)
        seen.add(text)
    return items


def build_system_spec(*, custom_operator_paths: Iterable[Any] | None = None) -> Dict[str, Any]:
    spec = SystemSpec(
        executor_type="default",
        np=1,
        open_tracer=False,
        custom_operator_paths=_normalize_string_list(custom_operator_paths),
        warnings=[SYSTEM_SPEC_DEFERRED_WARNING],
    )
    errors, warnings = validate_system_spec_payload(spec)
    return {
        "ok": len(errors) == 0,
        "system_spec": spec.to_dict(),
        "validation_errors": errors,
        "warnings": warnings,
        "message": "system spec built" if not errors else "system spec build failed",
    }


__all__ = ["build_system_spec"]
