# -*- coding: utf-8 -*-
"""Shared dataset-spec helpers for plan tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .._shared.schema import DatasetBindingSpec, DatasetSpec, _ALLOWED_MODALITIES


def _normalize_string_list(values: Iterable[Any] | None) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for item in values or []:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def infer_modality(binding: DatasetBindingSpec) -> str:
    candidate = str(binding.modality or "unknown").strip().lower()
    has_text = bool(binding.text_keys)
    has_image = bool(binding.image_key)
    has_audio = bool(binding.audio_key)
    has_video = bool(binding.video_key)

    if candidate in {"text", "image", "audio", "video", "multimodal"}:
        if candidate == "text" and has_text:
            return candidate
        if candidate == "image" and has_image:
            return candidate
        if candidate == "audio" and has_audio:
            return candidate
        if candidate == "video" and has_video:
            return candidate
        if candidate == "multimodal" and sum([has_text, has_image, has_audio, has_video]) >= 2:
            return candidate

    active_modalities = sum([has_text, has_image, has_audio, has_video])
    if active_modalities >= 2:
        return "multimodal"
    if has_video:
        return "video"
    if has_audio:
        return "audio"
    if has_image:
        return "image"
    if has_text:
        return "text"
    return "unknown"


def _dataset_source_priority_warning(source_count: int) -> str | None:
    if source_count <= 1:
        return None
    return (
        "multiple dataset sources are present; current implementation is local-path-first and will "
        "follow Data-Juicer source priority generated_dataset_config > dataset_path > dataset"
    )


def validate_dataset_spec_payload(
    dataset_spec: DatasetSpec | Dict[str, Any],
    *,
    dataset_profile: Dict[str, Any] | None = None,
) -> Tuple[List[str], List[str]]:
    if isinstance(dataset_spec, dict):
        dataset_spec = DatasetSpec.from_dict(dataset_spec)

    errors: List[str] = []
    warnings: List[str] = list(dataset_spec.warnings)
    io = dataset_spec.io
    binding = dataset_spec.binding

    source_count = int(bool(io.generated_dataset_config)) + int(bool(io.dataset_path)) + int(bool(io.dataset))
    source_warning = _dataset_source_priority_warning(source_count)
    if source_warning and source_warning not in warnings:
        warnings.append(source_warning)

    if io.dataset and not io.dataset_path:
        errors.append("dataset source objects are reserved for a later iteration; use dataset_path for now")
    if io.generated_dataset_config and not io.dataset_path:
        errors.append(
            "generated_dataset_config is reserved for a later iteration; use dataset_path for now"
        )
    if not io.dataset_path:
        errors.append("dataset_path is required in this iteration")
    if not io.export_path:
        errors.append("export_path is required")

    if io.dataset_path:
        dataset_path = Path(io.dataset_path).expanduser()
        if not dataset_path.exists():
            errors.append(f"dataset_path does not exist: {io.dataset_path}")

    if io.export_path:
        export_parent = Path(io.export_path).expanduser().resolve().parent
        if not export_parent.exists():
            errors.append(f"export parent directory does not exist: {export_parent}")

    if binding.modality not in _ALLOWED_MODALITIES:
        errors.append("modality must be one of text/image/audio/video/multimodal/unknown")
    if binding.modality == "text" and not binding.text_keys:
        errors.append("text modality requires text_keys")
    if binding.modality == "image" and not binding.image_key:
        errors.append("image modality requires image_key")
    if binding.modality == "audio" and not binding.audio_key:
        errors.append("audio modality requires audio_key")
    if binding.modality == "video" and not binding.video_key:
        errors.append("video modality requires video_key")
    if binding.modality == "multimodal":
        active = sum([bool(binding.text_keys), bool(binding.image_key), bool(binding.audio_key), bool(binding.video_key)])
        if active < 2:
            errors.append("multimodal modality requires at least two bound modalities")

    if isinstance(dataset_profile, dict) and dataset_profile.get("ok"):
        known_keys = set(dataset_profile.get("keys", [])) if isinstance(dataset_profile.get("keys", []), list) else set()
        for key in binding.text_keys:
            if known_keys and key not in known_keys:
                errors.append(f"text key not found in inspected dataset profile: {key}")
        for field_name, value in {
            "image_key": binding.image_key,
            "audio_key": binding.audio_key,
            "video_key": binding.video_key,
            "image_bytes_key": binding.image_bytes_key,
        }.items():
            if value and known_keys and value not in known_keys:
                errors.append(f"{field_name} not found in inspected dataset profile: {value}")

    dataset_cfg = io.dataset or {}
    if isinstance(dataset_cfg, dict) and isinstance(dataset_cfg.get("configs"), list):
        types = [item.get("type") for item in dataset_cfg.get("configs", []) if isinstance(item, dict)]
        normalized_types = {str(item).strip() for item in types if str(item).strip()}
        if len(normalized_types) > 1:
            errors.append("mixture of different dataset source types is not supported")
        if normalized_types == {"remote"} and len(dataset_cfg.get("configs", [])) > 1:
            errors.append("multiple remote datasets are not supported")

    return errors, warnings


__all__ = ["infer_modality", "validate_dataset_spec_payload"]
