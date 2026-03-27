# -*- coding: utf-8 -*-
"""Input models for list_dataset_load_strategies."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ListDatasetLoadStrategiesInput(BaseModel):
    """Input for list_dataset_load_strategies.

    Discovers which dataset loading strategies are truly implemented in the
    current Data-Juicer installation. Use this BEFORE build_dataset_spec when
    you need to configure non-trivial dataset sources (e.g., remote S3, mixed
    weights). For simple single local files, use dataset_path directly.
    """

    executor_type: str = Field(
        default="default",
        description=(
            "Filter strategies by executor type. "
            "Use 'default' for standard local execution, 'ray' for distributed, "
            "or '*' to list strategies for all executor types."
        ),
    )
