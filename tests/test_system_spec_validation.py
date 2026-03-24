# -*- coding: utf-8 -*-
"""Tests for system_spec semantic validation rules.

Covers 5 rules mirrored from DJ init_setup_from_cfg:
  - np <= CPU core count (auto-correction in normalize)
  - cache/checkpoint mutual exclusion (auto-correction in normalize)
  - op_fusion/checkpoint mutual exclusion (auto-correction in normalize)
  - fusion_strategy legality (hard error in validate)
  - work_dir {job_id} position (hard error in validate)
"""

import os
from unittest.mock import patch

from data_juicer_agents.tools.plan._shared.schema import SystemSpec
from data_juicer_agents.tools.plan._shared.system_spec import (
    normalize_system_spec,
    validate_system_spec_payload,
)


# ---------------------------------------------------------------------------
# normalize: np <= CPU core count
# ---------------------------------------------------------------------------

def test_normalize_caps_np_to_cpu_count():
    """np exceeding CPU count is capped and a warning is emitted."""
    with patch("os.cpu_count", return_value=4):
        spec = normalize_system_spec({"np": 128})
    assert spec.np == 4
    assert any("np=128" in w and "capped" in w for w in spec.warnings)


def test_normalize_np_within_limit_no_warning():
    """np within CPU count produces no auto-correction warning."""
    with patch("os.cpu_count", return_value=16):
        spec = normalize_system_spec({"np": 8})
    assert spec.np == 8
    assert not any("capped" in w for w in spec.warnings)


# ---------------------------------------------------------------------------
# normalize: cache / checkpoint mutual exclusion
# ---------------------------------------------------------------------------

def test_normalize_disables_cache_compress_when_cache_off():
    """cache_compress is cleared when use_cache=False."""
    spec = normalize_system_spec({
        "use_cache": False,
        "cache_compress": "zstd",
    })
    assert spec.get("cache_compress") is None
    assert any("cache_compress disabled" in w for w in spec.warnings)


def test_normalize_disables_cache_compress_when_checkpoint_on():
    """cache_compress is cleared when use_checkpoint=True."""
    spec = normalize_system_spec({
        "use_checkpoint": True,
        "cache_compress": "zstd",
    })
    assert spec.get("cache_compress") is None
    assert any("cache_compress disabled" in w for w in spec.warnings)


def test_normalize_cache_compress_untouched_when_cache_on():
    """cache_compress is kept when cache is on and checkpoint is off."""
    spec = normalize_system_spec({
        "use_cache": True,
        "use_checkpoint": False,
        "cache_compress": "zstd",
    })
    assert spec.get("cache_compress") == "zstd"
    assert not any("cache_compress disabled" in w for w in spec.warnings)


# ---------------------------------------------------------------------------
# normalize: op_fusion / checkpoint mutual exclusion
# ---------------------------------------------------------------------------

def test_normalize_disables_checkpoint_when_op_fusion_on():
    """use_checkpoint is forced off when op_fusion is enabled."""
    spec = normalize_system_spec({
        "op_fusion": True,
        "use_checkpoint": True,
    })
    assert spec.get("use_checkpoint") is False
    assert any("use_checkpoint disabled" in w for w in spec.warnings)


def test_normalize_op_fusion_off_keeps_checkpoint():
    """use_checkpoint is untouched when op_fusion is off."""
    spec = normalize_system_spec({
        "op_fusion": False,
        "use_checkpoint": True,
    })
    assert spec.get("use_checkpoint") is True
    assert not any("use_checkpoint disabled" in w for w in spec.warnings)


# ---------------------------------------------------------------------------
# validate: fusion_strategy legality
# ---------------------------------------------------------------------------

def test_validate_rejects_invalid_fusion_strategy():
    """Invalid fusion_strategy produces an error when op_fusion is on."""
    spec = SystemSpec.from_dict({
        "op_fusion": True,
        "fusion_strategy": "nonexistent_strategy",
    })
    errors, _ = validate_system_spec_payload(spec)
    assert any("fusion_strategy" in e and "nonexistent_strategy" in e for e in errors)


def test_validate_accepts_valid_fusion_strategy():
    """Valid fusion_strategy ('greedy') produces no fusion_strategy error."""
    spec = SystemSpec.from_dict({
        "op_fusion": True,
        "fusion_strategy": "greedy",
    })
    errors, _ = validate_system_spec_payload(spec)
    assert not any("fusion_strategy" in e for e in errors)


def test_validate_skips_fusion_strategy_when_op_fusion_off():
    """fusion_strategy is not checked when op_fusion is off."""
    spec = SystemSpec.from_dict({
        "op_fusion": False,
        "fusion_strategy": "totally_invalid",
    })
    errors, _ = validate_system_spec_payload(spec)
    assert not any("fusion_strategy" in e for e in errors)


# ---------------------------------------------------------------------------
# validate: work_dir {job_id} position
# ---------------------------------------------------------------------------

def test_validate_rejects_job_id_not_at_end():
    """{job_id} not at the end of work_dir produces an error."""
    spec = SystemSpec.from_dict({
        "work_dir": "/data/{job_id}/outputs",
    })
    errors, _ = validate_system_spec_payload(spec)
    assert any("{job_id}" in e and "last" in e for e in errors)


def test_validate_accepts_job_id_at_end():
    """{job_id} at the end of work_dir is accepted."""
    spec = SystemSpec.from_dict({
        "work_dir": "/data/outputs/{job_id}",
    })
    errors, _ = validate_system_spec_payload(spec)
    assert not any("{job_id}" in e for e in errors)


def test_validate_no_error_when_work_dir_has_no_job_id():
    """work_dir without {job_id} produces no related error."""
    spec = SystemSpec.from_dict({
        "work_dir": "/data/outputs/my_project",
    })
    errors, _ = validate_system_spec_payload(spec)
    assert not any("{job_id}" in e for e in errors)
