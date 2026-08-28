# -*- coding: utf-8 -*-
"""E2E tests pinning validate_dataset_spec_payload behavior before preflight cleanup."""

from data_juicer_agents.tools.plan._shared.dataset_spec import (
    normalize_dataset_spec,
    validate_dataset_spec_payload,
)
from data_juicer_agents.tools.plan._shared.schema import DatasetSpec


class TestValidateDatasetSpec:
    """Pin current behavior of validate_dataset_spec_payload."""

    def test_no_source_error(self):
        spec = DatasetSpec.from_dict({
            "io": {"dataset_path": "", "export_path": "/tmp/out"},
            "binding": {"modality": "text", "text_keys": ["text"]},
        })
        errors, warnings = validate_dataset_spec_payload(spec)
        assert any("at least one dataset source" in e for e in errors)

    def test_nonexistent_dataset_path_error(self):
        spec = DatasetSpec.from_dict({
            "io": {"dataset_path": "/nonexistent/path.jsonl", "export_path": "/tmp/out"},
            "binding": {"modality": "text", "text_keys": ["text"]},
        })
        errors, warnings = validate_dataset_spec_payload(spec)
        assert any("does not exist" in e and "/nonexistent/path.jsonl" in e for e in errors)

    def test_missing_export_path_error(self):
        spec = DatasetSpec.from_dict({
            "io": {"dataset_path": "/tmp", "export_path": ""},
            "binding": {"modality": "text", "text_keys": ["text"]},
        })
        errors, warnings = validate_dataset_spec_payload(spec)
        assert any("export_path is required" in e for e in errors)

    def test_image_modality_requires_image_key(self):
        spec = DatasetSpec.from_dict({
            "io": {"dataset_path": "/tmp", "export_path": "/tmp/out"},
            "binding": {"modality": "image", "text_keys": ["text"]},
        })
        errors, warnings = validate_dataset_spec_payload(spec)
        assert any("image modality requires image_key" in e for e in errors)

    def test_multimodal_needs_two_bindings(self):
        spec = DatasetSpec.from_dict({
            "io": {"dataset_path": "/tmp", "export_path": "/tmp/out"},
            "binding": {"modality": "multimodal", "text_keys": ["text"]},
        })
        errors, warnings = validate_dataset_spec_payload(spec)
        assert any("at least two bound modalities" in e for e in errors)

    def test_multiple_sources_warning(self):
        spec = DatasetSpec.from_dict({
            "io": {
                "dataset_path": "/tmp",
                "dataset": {"configs": [{"type": "local", "path": "/tmp/a.jsonl"}]},
                "export_path": "/tmp/out",
            },
            "binding": {"modality": "text", "text_keys": ["text"]},
        })
        errors, warnings = validate_dataset_spec_payload(spec)
        assert any("multiple dataset sources" in w for w in warnings)

    def test_bad_load_strategy_detected(self):
        spec = DatasetSpec.from_dict({
            "io": {
                "dataset": {"configs": [{"type": "local", "source": "nonexistent_source", "path": "/tmp/a.jsonl"}]},
                "export_path": "/tmp/out",
            },
            "binding": {"modality": "text", "text_keys": ["text"]},
        })
        errors, warnings = validate_dataset_spec_payload(spec)
        assert any("not implemented" in e.lower() for e in errors)

    def test_dataset_profile_key_mismatch(self):
        spec = DatasetSpec.from_dict({
            "io": {"dataset_path": "/tmp", "export_path": "/tmp/out"},
            "binding": {"modality": "text", "text_keys": ["content"]},
        })
        profile = {"ok": True, "keys": ["text", "meta"]}
        errors, warnings = validate_dataset_spec_payload(spec, dataset_profile=profile)
        assert any("content" in e and "not found" in e for e in errors)

    def test_valid_text_spec_passes(self):
        spec = DatasetSpec.from_dict({
            "io": {"dataset_path": "/tmp", "export_path": "/tmp/out"},
            "binding": {"modality": "text", "text_keys": ["text"]},
        })
        errors, warnings = validate_dataset_spec_payload(spec)
        assert errors == []

    def test_audio_modality_requires_audio_key(self):
        spec = DatasetSpec.from_dict({
            "io": {"dataset_path": "/tmp", "export_path": "/tmp/out"},
            "binding": {"modality": "audio"},
        })
        errors, warnings = validate_dataset_spec_payload(spec)
        assert any("audio modality requires audio_key" in e for e in errors)

    def test_video_modality_requires_video_key(self):
        spec = DatasetSpec.from_dict({
            "io": {"dataset_path": "/tmp", "export_path": "/tmp/out"},
            "binding": {"modality": "video"},
        })
        errors, warnings = validate_dataset_spec_payload(spec)
        assert any("video modality requires video_key" in e for e in errors)


class TestNormalizeDatasetSpec:
    """Pin normalize_dataset_spec behavior."""

    def test_strips_paths(self):
        spec = DatasetSpec.from_dict({
            "io": {"dataset_path": "  /tmp/data.jsonl  ", "export_path": "  /tmp/out  "},
            "binding": {"modality": "text", "text_keys": ["text"]},
        })
        result = normalize_dataset_spec(spec)
        assert result.io.dataset_path == "/tmp/data.jsonl"
        assert result.io.export_path == "/tmp/out"

    def test_preserves_extra_fields(self):
        spec = DatasetSpec.from_dict({
            "io": {
                "dataset_path": "/tmp/data.jsonl",
                "export_path": "/tmp/out",
                "export_type": "jsonl",
                "suffixes": [".jsonl"],
            },
            "binding": {"modality": "text", "text_keys": ["text"]},
        })
        result = normalize_dataset_spec(spec)
        assert result.io._extra_fields.get("export_type") == "jsonl"
        assert result.io._extra_fields.get("suffixes") == [".jsonl"]
