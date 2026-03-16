# -*- coding: utf-8 -*-
"""Input models for build_dataset_spec."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class BuildDatasetSpecInput(BaseModel):
    intent: str = Field(description="User intent for the current planning task.")
    dataset_path: str = Field(description="Input dataset path.")
    export_path: str = Field(description="Output dataset path.")
    dataset_profile: Dict[str, Any] = Field(
        description="Dataset inspection payload returned by inspect_dataset.",
    )
    modality_hint: str = Field(default="", description="Optional explicit modality override.")
    text_keys_hint: List[str] = Field(default_factory=list, description="Optional text key overrides.")
    image_key_hint: str = Field(default="", description="Optional image key override.")
    audio_key_hint: str = Field(default="", description="Optional audio key override.")
    video_key_hint: str = Field(default="", description="Optional video key override.")
    image_bytes_key_hint: str = Field(default="", description="Optional image-bytes key override.")
