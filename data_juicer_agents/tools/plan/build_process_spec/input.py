# -*- coding: utf-8 -*-
"""Input models for build_process_spec."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ProcessOperatorInput(BaseModel):
    name: str = Field(description="Canonical operator name.")
    params: Dict[str, Any] = Field(
        description=(
            "Operator-specific params object. Fill suitable concrete params for this operator "
            "based on the user request, dataset context, and retrieve_operators results. "
            "If a threshold, mode, or explicit option is already known, include it here."
        ),
    )


class BuildProcessSpecInput(BaseModel):
    operators: List[ProcessOperatorInput] = Field(
        description=(
            "Ordered operators for this plan. Choose canonical names from retrieve_operators "
            "results and fill appropriate params for each operator."
        ),
    )
    custom_operator_paths: Optional[List[str]] = Field(
        default=None,
        description=(
            "Optional list of directory paths containing custom operators. "
            "Example: ['./custom_ops', './my_operators']. "
            "When provided, custom operators are loaded into the registry before validation."
        ),
    )

    @field_validator("custom_operator_paths", mode="before")
    @classmethod
    def _coerce_string_to_list(cls, value: Any) -> Any:
        """Handle LLMs that serialise a list as a JSON string.

        Some models produce ``'["./path"]'`` (a string) instead of
        ``["./path"]`` (a list) when the JSON Schema uses ``anyOf``
        for ``Optional[List[str]]``.
        """
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
        return [stripped] if stripped else None
