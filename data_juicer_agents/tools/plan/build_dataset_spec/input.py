import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from data_juicer_agents.core.tool import DatasetSource


class BuildDatasetSpecInput(BaseModel):
    model_config = ConfigDict(extra="allow")  # Allow advanced dataset fields as extra kwargs

    intent: str = Field(
        description=(
            "User intent for the current planning task. "
            "For advanced dataset options (e.g., export_type, export_shard_size, "
            "export_in_parallel, load_dataset_kwargs, suffixes, image_special_token, etc.), "
            "call list_dataset_fields first to discover available fields, "
            "then pass them directly as additional arguments to this tool."
        )
    )
    export_path: str = Field(description="Output dataset path.")
    dataset_source: DatasetSource = Field(
        description=(
            "Dataset source specification.  Provide exactly one of: "
            "path (local file/directory shortcut), "
            "config (structured load config for remote sources, multi-source mixing, "
            "max_sample_num, per-source weights — call list_dataset_load_strategies to "
            "discover available types/sources), "
            "or generated (dynamic formatter config — call list_dataset_formatters to "
            "discover available formatters and parameters)."
        ),
    )
    dataset_profile: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dataset inspection payload returned by inspect_dataset.",
    )
    modality_hint: str = Field(default="", description="Optional explicit modality override.")
    text_keys_hint: List[str] = Field(default_factory=list, description="Optional text key overrides.")
    image_key_hint: str = Field(default="", description="Optional image key override.")
    audio_key_hint: str = Field(default="", description="Optional audio key override.")
    video_key_hint: str = Field(default="", description="Optional video key override.")
    image_bytes_key_hint: str = Field(default="", description="Optional image-bytes key override.")
