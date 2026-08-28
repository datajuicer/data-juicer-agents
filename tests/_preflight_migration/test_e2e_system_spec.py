# -*- coding: utf-8 -*-
"""E2E tests pinning validate_system_spec_payload and normalize_system_spec behavior."""

import os

from data_juicer_agents.tools.plan._shared.schema import SystemSpec
from data_juicer_agents.tools.plan._shared.system_spec import (
    normalize_system_spec,
    validate_system_spec_payload,
)


class TestValidateSystemSpec:
    """Pin current behavior of validate_system_spec_payload."""

    def test_valid_spec_passes(self):
        spec = SystemSpec(executor_type="default", np=4)
        errors, warnings = validate_system_spec_payload(spec)
        assert errors == []

    def test_np_zero_error(self):
        spec = SystemSpec(executor_type="default", np=0)
        errors, warnings = validate_system_spec_payload(spec)
        assert any("np must be >= 1" in e for e in errors)

    def test_empty_executor_type_error(self):
        spec = SystemSpec(executor_type="", np=1)
        errors, warnings = validate_system_spec_payload(spec)
        assert any("executor_type is required" in e for e in errors)

    def test_bad_fusion_strategy_error(self):
        spec = SystemSpec(
            executor_type="default", np=1,
            _extra_fields={"op_fusion": True, "fusion_strategy": "nonexistent_strategy"},
        )
        errors, warnings = validate_system_spec_payload(spec)
        assert any("nonexistent_strategy" in e and "not supported" in e for e in errors)

    def test_valid_fusion_strategy_passes(self):
        spec = SystemSpec(
            executor_type="default", np=1,
            _extra_fields={"op_fusion": True, "fusion_strategy": "greedy"},
        )
        errors, warnings = validate_system_spec_payload(spec)
        assert not any("fusion_strategy" in e for e in errors)

    def test_work_dir_placeholder_error(self):
        spec = SystemSpec(
            executor_type="default", np=1,
            _extra_fields={"work_dir": "/data/{job_id}/subdir"},
        )
        errors, warnings = validate_system_spec_payload(spec)
        assert any("{job_id}" in e and "last component" in e for e in errors)

    def test_work_dir_placeholder_valid(self):
        spec = SystemSpec(
            executor_type="default", np=1,
            _extra_fields={"work_dir": "/data/{job_id}"},
        )
        errors, warnings = validate_system_spec_payload(spec)
        assert not any("{job_id}" in e for e in errors)


class TestNormalizeSystemSpec:
    """Pin current behavior of normalize_system_spec."""

    def test_np_capped_to_cpu_count(self):
        cpu_count = os.cpu_count() or 1
        spec = SystemSpec(executor_type="default", np=9999)
        result = normalize_system_spec(spec)
        assert result.np == cpu_count
        assert any("np=" in w and "capped" in w for w in result.warnings)

    def test_cache_compress_disabled_when_cache_off(self):
        spec = SystemSpec(
            executor_type="default", np=1,
            _extra_fields={"use_cache": False, "cache_compress": "zstd"},
        )
        result = normalize_system_spec(spec)
        assert result.get("cache_compress") is None
        assert any("cache_compress disabled" in w for w in result.warnings)

    def test_checkpoint_disabled_when_op_fusion(self):
        spec = SystemSpec(
            executor_type="default", np=1,
            _extra_fields={"op_fusion": True, "use_checkpoint": True},
        )
        result = normalize_system_spec(spec)
        assert result.get("use_checkpoint") is False
        assert any("use_checkpoint disabled" in w for w in result.warnings)

    def test_custom_operator_paths_override(self):
        spec = SystemSpec(executor_type="default", np=1, custom_operator_paths=["/old/path"])
        result = normalize_system_spec(spec, custom_operator_paths=["/new/path"])
        assert result.custom_operator_paths == ["/new/path"]

    def test_np_within_limit_unchanged(self):
        spec = SystemSpec(executor_type="default", np=2)
        result = normalize_system_spec(spec)
        assert result.np == 2
        assert not any("np=" in w for w in result.warnings)
