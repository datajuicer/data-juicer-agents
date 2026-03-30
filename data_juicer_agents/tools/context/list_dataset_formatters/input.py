# -*- coding: utf-8 -*-
"""Input models for list_dataset_formatters."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ListDatasetFormattersInput(BaseModel):
    """Input for list_dataset_formatters.

    Discovers which dataset formatters (dynamic data generators) are available
    in the current Data-Juicer installation. Use this BEFORE build_dataset_spec
    when you need to configure the generated_dataset_config field for dynamic
    dataset generation (e.g., EmptyFormatter for creating empty datasets).
    """

    include_ray: bool = Field(
        default=True,
        description=(
            "Whether to include Ray-specific formatters in the results. "
            "Set to False to only show standard (non-Ray) formatters."
        ),
    )
