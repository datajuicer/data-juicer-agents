# -*- coding: utf-8 -*-
"""Input models for list_dataset_fields."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ListDatasetFieldsInput(BaseModel):
    """Input for list_dataset_fields.

    This tool lists all dataset-related configuration fields recognized by
    Data-Juicer, including their types, default values, and descriptions.
    Use this before build_dataset_spec to discover advanced dataset options
    such as export_type, export_shard_size, load_dataset_kwargs, suffixes,
    or modality special tokens.
    """

    filter_prefix: Optional[str] = Field(
        None,
        description=(
            "Optional filter to show only parameters matching this prefix "
            "(e.g., 'export_' for export-related fields, 'image_' for image fields)."
        ),
    )

    include_descriptions: bool = Field(
        True,
        description="Whether to include parameter descriptions. Default is True.",
    )
