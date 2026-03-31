import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    dataset_path: str = Field(
        default="",
        description=(
            "Shortcut for a single local file or directory. "
            "For advanced configs (mixed sources, per-source weights, max_sample_num), "
            "use the 'dataset' field instead."
        ),
    )
    dataset: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "YAML-style complex dataset config. Use this for multi-source mixing, "
            "per-source weights, or limiting max_sample_num. "
            "Call list_dataset_load_strategies first to discover available types/sources and their extra fields. "
            "Top-level keys: 'configs' (required list), 'max_sample_num' (optional int). "
            "Each entry in 'configs' supports: "
            "'type' (required str, e.g. 'local'), "
            "'path' (str, path to file/dir), "
            "'source' (str, sub-source specifier, e.g. 'file'/'s3'), "
            "'weight' (float, sampling weight), "
            "'split' (str, dataset split), "
            "plus any strategy-specific extra fields from list_dataset_load_strategies. "
            'Example: {"configs": [{"type": "local", "path": "/data/a.jsonl", "weight": 0.7}, '
            '{"type": "local", "path": "/data/b.jsonl", "weight": 0.3}], "max_sample_num": 50000}'
        ),
    )
    generated_dataset_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Config for dynamically generated datasets via Data-Juicer FORMATTERS. "
            "Must contain a 'type' key matching a registered formatter name. "
            "Call list_dataset_formatters first to discover available formatters and their parameters."
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

    @field_validator("dataset", "generated_dataset_config", mode="before")
    @classmethod
    def _coerce_json_string(cls, v: Any) -> Any:
        """Allow LLMs to pass JSON strings instead of dicts."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
        return v