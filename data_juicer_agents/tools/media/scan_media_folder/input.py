# -*- coding: utf-8 -*-
"""Input models for scan_media_folder."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ScanMediaFolderInput(BaseModel):
    """Input for scanning a local folder of raw images or videos."""

    folder_path: str = Field(description="Absolute or relative path to the media folder to scan.")
    media_type: Literal["image", "video", "auto"] = Field(
        default="auto",
        description="Type of media to scan. 'auto' detects images and videos together.",
    )
    recursive: bool = Field(default=True, description="Whether to descend into sub-directories.")
    output_path: str = Field(description="Destination JSONL file path to write the generated DJ-Format dataset.")
    suffixes: Optional[List[str]] = Field(
        default=None,
        description=(
            "Custom file extensions to include (e.g. ['.jpg', '.png']). "
            "Defaults to all common image/video suffixes depending on media_type."
        ),
    )


class ScanMediaFolderOutput(BaseModel):
    """Summary returned after a successful scan."""

    ok: bool = True
    record_count: int = Field(default=0, description="Number of records written to the JSONL file.")
    output_path: str = Field(default="", description="Absolute path of the generated JSONL file.")
    sample_records: list = Field(default_factory=list, description="Up to 3 sample records from the generated file.")
    media_type_detected: str = Field(default="", description="Detected media type label ('image', 'video', or 'mixed').")
