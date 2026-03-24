from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Dict

from .._shared.dataset_spec import infer_modality, validate_dataset_spec_payload
from .._shared.normalize import normalize_string_list
from .._shared.schema import DatasetSpec


def build_dataset_spec(    *,
    user_intent: str,
    dataset_path: str,
    export_path: str,
    dataset_profile: Dict[str, Any] | None = None,
    modality_hint: str = "",
    text_keys_hint: Iterable[Any] | None = None,
    image_key_hint: str = "",
    audio_key_hint: str = "",
    video_key_hint: str = "",
    image_bytes_key_hint: str = "",
) -> Dict[str, Any]:
    dataset_path = str(dataset_path or "").strip()
    export_path = str(export_path or "").strip()
    if not dataset_path:
        return {
            "ok": False,
            "error_type": "missing_required",
            "message": "dataset_path is required for build_dataset_spec",
            "requires": ["dataset_path"],
        }
    if not export_path:
        return {
            "ok": False,
            "error_type": "missing_required",
            "message": "export_path is required for build_dataset_spec",
            "requires": ["export_path"],
        }

    profile = dataset_profile if isinstance(dataset_profile, dict) else {}
    candidate_text = profile.get("candidate_text_keys", []) if isinstance(profile.get("candidate_text_keys"), list) else []
    candidate_image = profile.get("candidate_image_keys", []) if isinstance(profile.get("candidate_image_keys"), list) else []
    requested_modality = str(modality_hint or "").strip().lower()

    text_keys = normalize_string_list(text_keys_hint) or normalize_string_list(candidate_text)
    image_key = str(image_key_hint or "").strip() or (str(candidate_image[0]).strip() if candidate_image else "")
    audio_key = str(audio_key_hint or "").strip()
    video_key = str(video_key_hint or "").strip()
    image_bytes_key = str(image_bytes_key_hint or "").strip()

    modality = requested_modality
    if modality not in {"text", "image", "audio", "video", "multimodal", "unknown"}:
        modality = str(profile.get("modality", "unknown") or "unknown").strip().lower() or "unknown"
    if modality == "unknown":
        modality = infer_modality(
            DatasetSpec.from_dict(
                {
                    "io": {"dataset_path": dataset_path, "export_path": export_path},
                    "binding": {
                        "modality": "unknown",
                        "text_keys": list(text_keys),
                        "image_key": image_key,
                        "audio_key": audio_key,
                        "video_key": video_key,
                        "image_bytes_key": image_bytes_key,
                    },
                }
            ).binding
        )

    spec = DatasetSpec.from_dict(
        {
            "io": {
                "dataset_path": dataset_path,
                "export_path": export_path,
            },
            "binding": {
                "modality": modality,
                "text_keys": list(text_keys),
                "image_key": image_key,
                "audio_key": audio_key,
                "video_key": video_key,
                "image_bytes_key": image_bytes_key,
            },
        }
    )
    errors, warnings = validate_dataset_spec_payload(spec, dataset_profile=profile)
    return {
        "ok": len(errors) == 0,
        "dataset_spec": spec.to_dict(),
        "validation_errors": errors,
        "warnings": warnings,
        "message": "dataset spec built" if not errors else "dataset spec build failed",
        "intent": str(user_intent or "").strip(),
    }


__all__ = ["build_dataset_spec"]
