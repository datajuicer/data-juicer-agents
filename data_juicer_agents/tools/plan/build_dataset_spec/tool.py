# -*- coding: utf-8 -*-
"""Tool spec for build_dataset_spec."""

from __future__ import annotations

from pydantic import BaseModel

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import BuildDatasetSpecInput
from .logic import build_dataset_spec


class GenericOutput(BaseModel):
    ok: bool = True


def _build_dataset_spec(_ctx: ToolContext, args: BuildDatasetSpecInput) -> ToolResult:
    result = build_dataset_spec(
        user_intent=args.intent,
        dataset_path=args.dataset_path,
        dataset=args.dataset,
        generated_dataset_config=args.generated_dataset_config,
        export_path=args.export_path,
        dataset_profile=args.dataset_profile,
        modality_hint=args.modality_hint,
        text_keys_hint=args.text_keys_hint,
        image_key_hint=args.image_key_hint,
        audio_key_hint=args.audio_key_hint,
        video_key_hint=args.video_key_hint,
        image_bytes_key_hint=args.image_bytes_key_hint,
    )
    if result.get("ok"):
        return ToolResult.success(summary=str(result.get("message", "dataset spec built")), data=result)
    return ToolResult.failure(
        summary=str(result.get("message", "dataset spec build failed")),
        error_type=str(result.get("error_type", "build_dataset_spec_failed")),
        error_message=str(result.get("error_message", "")).strip(),
        data=result,
    )

BUILD_DATASET_SPEC = ToolSpec(
    name="build_dataset_spec",
    description=(
        "Build a deterministic dataset spec from an explicit user intent and export_path. "
        "Accepts dataset_path (shortcut for a single local file), dataset (YAML-style complex config "
        "for mixed sources/weights/max_sample_num), or generated_dataset_config (dynamic formatter config). "
        "For non-trivial dataset sources, call list_dataset_load_strategies first to discover "
        "available types/sources."
    ),
    input_model=BuildDatasetSpecInput,
    output_model=GenericOutput,
    executor=_build_dataset_spec,
    tags=("plan",),
    effects="write",
    confirmation="none",
)


__all__ = ["BUILD_DATASET_SPEC"]
