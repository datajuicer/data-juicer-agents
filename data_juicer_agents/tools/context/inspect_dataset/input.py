# -*- coding: utf-8 -*-
"""Input models for inspect_dataset."""

from __future__ import annotations

from pydantic import BaseModel, Field

from data_juicer_agents.core.tool import DatasetSource


class InspectDatasetInput(BaseModel):
    dataset_source: DatasetSource = Field(
        description=(
            "Dataset to inspect.  Provide exactly one of: "
            "path (local file shortcut), config (structured load config), "
            "or generated (dynamic formatter config)."
        ),
    )
    sample_size: int = Field(default=20, ge=1, description="Number of samples to inspect.")


class GenericOutput(BaseModel):
    ok: bool = True