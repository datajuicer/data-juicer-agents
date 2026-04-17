# -*- coding: utf-8 -*-
"""Unified dataset source descriptor.

Replaces the scattered ``dataset_path`` / ``dataset`` /
``generated_dataset_config`` triple with a single, self-describing envelope
object.  The envelope only enforces the *exactly-one-of-three* constraint;
the inner schema of ``config`` and ``generated`` is **not** duplicated here
— it stays in :class:`DatasetObjectConfig` and
:class:`GeneratedDatasetConfig` respectively and is validated when the
envelope is converted to a :class:`DatasetIOSpec` via :meth:`to_io_spec`.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class DatasetSource(BaseModel):
    """Unified dataset source envelope.

    Exactly **one** of ``path``, ``config``, or ``generated`` must be
    provided.  Providing zero or more than one raises a validation error.

    Examples::

        # Simple local file (shortcut)
        DatasetSource(path="/data/train.jsonl")

        # Structured load config (remote, multi-source, max_sample_num …)
        DatasetSource(config={
            "configs": [
                {"type": "local", "path": "/data/a.jsonl", "weight": 0.7},
                {"type": "local", "path": "/data/b.jsonl", "weight": 0.3},
            ],
            "max_sample_num": 50000,
        })

        # Dynamic generation via Data-Juicer FORMATTERS
        DatasetSource(generated={"type": "text_formatter", ...})
    """

    path: str = Field(
        default="",
        description=(
            "Local file or directory path (shortcut for simple single-source cases). "
            "Example: '/data/train.jsonl'"
        ),
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Structured dataset load config (same schema as the 'dataset' block in a "
            "Data-Juicer recipe).  Use for remote sources, multi-source mixing, "
            "max_sample_num, per-source weights, etc.  "
            "Run list_dataset_load_strategies to discover available source types and fields.  "
            'Example: {"configs": [{"type": "local", "path": "...", "weight": 0.7}], '
            '"max_sample_num": 5000}'
        ),
    )
    generated: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Dynamic dataset generator config via Data-Juicer FORMATTERS.  "
            "Must contain a 'type' key matching a registered formatter name.  "
            "Run list_dataset_formatters to discover available formatters and parameters.  "
            'Example: {"type": "text_formatter", ...}'
        ),
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("config", "generated", mode="before")
    @classmethod
    def _coerce_json_string(cls, value: Any) -> Any:
        """Allow LLMs to pass JSON strings instead of dicts.

        Raises:
            ValueError: When the string is not valid JSON or does not parse to a dict.
        """
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
                raise ValueError(
                    f"Expected a JSON object (dict), got {type(parsed).__name__}: {value!r}"
                )
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON string for dataset config: {value!r}. "
                    f"Provide a valid JSON object or a dict directly. Details: {exc}"
                ) from exc
        return value

    @model_validator(mode="after")
    def _validate_exactly_one_source(self) -> "DatasetSource":
        provided = [
            name
            for name, present in [
                ("path", bool(self.path)),
                ("config", self.config is not None),
                ("generated", self.generated is not None),
            ]
            if present
        ]
        if len(provided) == 0:
            raise ValueError(
                "Exactly one dataset source is required: "
                "provide one of path, config, or generated."
            )
        if len(provided) > 1:
            raise ValueError(
                f"Only one dataset source can be specified at a time, "
                f"but got {len(provided)}: {', '.join(provided)}. "
                f"Please provide only one of path, config, or generated."
            )
        return self

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def to_legacy_args(self) -> Dict[str, Any]:
        """Convert to the legacy ``(dataset_path, dataset, generated_dataset_config)`` dict.

        Returns a dict with exactly the three legacy keys so callers can
        unpack with ``**source.to_legacy_args()``.
        """
        return {
            "dataset_path": self.path,
            "dataset": self.config,
            "generated_dataset_config": self.generated,
        }

    @classmethod
    def from_legacy(
        cls,
        dataset_path: str = "",
        dataset: Dict[str, Any] | None = None,
        generated_dataset_config: Dict[str, Any] | None = None,
    ) -> "DatasetSource":
        """Create a :class:`DatasetSource` from the legacy triple.

        This is the primary migration bridge: CLI argument parsers and
        existing callers can keep their three-parameter interface and
        convert to the unified envelope at the boundary.
        """
        return cls(
            path=str(dataset_path or "").strip(),
            config=dataset,
            generated=generated_dataset_config,
        )


__all__ = ["DatasetSource"]
