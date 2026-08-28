# -*- coding: utf-8 -*-

from pathlib import Path

import yaml

from data_juicer_agents.tools.apply.submit_ray_job.logic import (
    _classify_ray_error,
    _rewrite_dedup_ops_for_ray,
    _to_dj_process,
    _uniquify_export_path,
    _write_recipe,
)


# ---------------------------------------------------------------------------
# _to_dj_process
# ---------------------------------------------------------------------------


def test_to_dj_process_agent_internal_form():
    raw = [
        {"name": "text_length_filter", "params": {"min_len": 10}},
        {"name": "whitespace_normalization_mapper", "params": None},
    ]
    assert _to_dj_process(raw) == [
        {"text_length_filter": {"min_len": 10}},
        {"whitespace_normalization_mapper": {}},
    ]


def test_to_dj_process_dj_native_form_passthrough():
    raw = [{"text_length_filter": {"min_len": 10}}]
    assert _to_dj_process(raw) == raw


def test_to_dj_process_skips_invalid_steps():
    raw = [
        "not-a-dict",
        {"name": "   "},
        {"a": 1, "b": 2},  # multi-key dict without "name" is ambiguous
        {"image_deduplicator": {}},
    ]
    assert _to_dj_process(raw) == [{"image_deduplicator": {}}]


# ---------------------------------------------------------------------------
# _rewrite_dedup_ops_for_ray
# ---------------------------------------------------------------------------


def test_rewrite_dedup_ops_maps_to_ray_native():
    process = [
        {"image_deduplicator": {"method": "phash"}},
        {"document_deduplicator": {"lowercase": True}},
        {"video_deduplicator": {}},
    ]
    assert _rewrite_dedup_ops_for_ray(process) == [
        {"ray_image_deduplicator": {"method": "phash"}},
        {"ray_document_deduplicator": {"lowercase": True}},
        {"ray_video_deduplicator": {}},
    ]


def test_rewrite_dedup_ops_drops_incompatible_params():
    process = [{"image_deduplicator": {"method": "phash", "consider_text": True}}]
    assert _rewrite_dedup_ops_for_ray(process) == [
        {"ray_image_deduplicator": {"method": "phash"}}
    ]


def test_rewrite_dedup_ops_passes_through_other_ops():
    process = [
        {"text_length_filter": {"min_len": 10}},
        {"ray_image_deduplicator": {"method": "phash"}},  # idempotent
        {"document_minhash_deduplicator": {"jaccard_threshold": 0.7}},  # excluded
    ]
    assert _rewrite_dedup_ops_for_ray(process) == process


def test_rewrite_dedup_ops_does_not_mutate_input():
    params = {"method": "phash", "consider_text": True}
    process = [{"image_deduplicator": params}]
    _rewrite_dedup_ops_for_ray(process)
    assert params == {"method": "phash", "consider_text": True}


# ---------------------------------------------------------------------------
# _write_recipe
# ---------------------------------------------------------------------------


def _base_plan() -> dict:
    return {
        "plan_id": "demo_plan",
        "recipe": {
            "dataset_path": "/mnt/data/input.jsonl",
            "export_path": "/mnt/data/out.jsonl",
            "process": [{"name": "image_deduplicator", "params": {"method": "phash"}}],
            "eoc_special_token": "<eoc>",  # not in _RECIPE_ALLOWED_KEYS
        },
    }


def test_write_recipe_forces_ray_executor_and_exec_scoped_work_dir(tmp_path: Path):
    recipe_path = _write_recipe(_base_plan(), tmp_path, "ray_abc12345")
    written = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))

    assert recipe_path.name == "demo_plan.yaml"
    assert written["executor_type"] == "ray"
    assert written["project_name"] == "demo_plan"
    # work_dir must be unique per submission (exec_id), not just per plan.
    assert written["work_dir"] == "/tmp/dj_work_demo_plan_ray_abc12345"


def test_write_recipe_rewrites_dedup_and_strips_unknown_keys(tmp_path: Path, caplog):
    with caplog.at_level("WARNING"):
        recipe_path = _write_recipe(_base_plan(), tmp_path, "ray_abc12345")
    written = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))

    assert written["process"] == [{"ray_image_deduplicator": {"method": "phash"}}]
    assert "eoc_special_token" not in written
    # Dropped keys must be surfaced, not silently discarded.
    assert "eoc_special_token" in caplog.text


def test_write_recipe_does_not_mutate_caller_recipe(tmp_path: Path):
    plan = _base_plan()
    original = dict(plan["recipe"])
    _write_recipe(plan, tmp_path, "ray_abc12345")
    assert plan["recipe"] == original


def test_write_recipe_rejects_missing_recipe(tmp_path: Path):
    try:
        _write_recipe({"plan_id": "p"}, tmp_path, "ray_abc12345")
    except ValueError as exc:
        assert "recipe" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing recipe")


# ---------------------------------------------------------------------------
# _uniquify_export_path
# ---------------------------------------------------------------------------


def test_uniquify_export_path_inserts_token_before_suffix():
    assert (
        _uniquify_export_path("/mnt/data/car_cleaned.jsonl", "ray_a1b2c3d4")
        == "/mnt/data/car_cleaned_ray_a1b2c3d4.jsonl"
    )


def test_uniquify_export_path_without_suffix():
    assert _uniquify_export_path("/mnt/data/out", "tok") == "/mnt/data/out_tok"


def test_uniquify_export_path_noop_on_empty_inputs():
    assert _uniquify_export_path("", "tok") == ""
    assert _uniquify_export_path("/mnt/data/out.jsonl", "") == "/mnt/data/out.jsonl"


# ---------------------------------------------------------------------------
# _classify_ray_error
# ---------------------------------------------------------------------------


def test_classify_ray_error_success():
    assert _classify_ray_error(0, "") == ("none", "")


def test_classify_ray_error_categories():
    assert _classify_ray_error(1, "ConnectionError: refused")[0] == "connection_failed"
    assert _classify_ray_error(1, "ray: no such file or directory")[0] == "command_not_found"
    assert _classify_ray_error(1, "failed to upload runtime_env")[0] == "packaging_failed"
    assert _classify_ray_error(1, "operation timeout")[0] == "timeout"
    error_type, message = _classify_ray_error(2, "something else")
    assert error_type == "submission_failed"
    assert "exit code 2" in message


# ---------------------------------------------------------------------------
# _build_ray_rewrite_map — dynamic discovery e2e tests
# ---------------------------------------------------------------------------

from data_juicer_agents.tools.apply.submit_ray_job.logic import _build_ray_rewrite_map


def test_build_ray_rewrite_map_discovers_expected_ops():
    """Dynamic discovery must produce the same result as the old hardcoded map."""
    rewrite, drop = _build_ray_rewrite_map()
    # Must find all three known dedup rewrites
    assert "image_deduplicator" in rewrite
    assert "document_deduplicator" in rewrite
    assert "video_deduplicator" in rewrite
    # Targets must be ray_ prefixed
    for std, ray in rewrite.items():
        assert ray == f"ray_{std}"


def test_build_ray_rewrite_map_detects_param_drops():
    """Dynamic param diff must detect consider_text as incompatible."""
    _, drop = _build_ray_rewrite_map()
    assert "consider_text" in drop.get("ray_image_deduplicator", set())
    assert "consider_text" in drop.get("ray_video_deduplicator", set())


def test_build_ray_rewrite_map_excludes_non_deduplicator_ray_ops():
    """ray_ ops that are not Deduplicator subclasses must not be rewritten."""
    rewrite, _ = _build_ray_rewrite_map()
    # All values in the rewrite map must correspond to Deduplicator subclasses
    from data_juicer.ops.base_op import OPERATORS, Deduplicator
    for std_name in rewrite:
        std_cls = OPERATORS.modules[std_name]
        assert issubclass(std_cls, Deduplicator), f"{std_name} is not a Deduplicator"


def test_build_ray_rewrite_map_graceful_without_dj(monkeypatch):
    """If DJ is not importable, function returns empty dicts (no crash)."""
    import builtins
    real_import = builtins.__import__

    def _block_dj(name, *args, **kwargs):
        if name.startswith("data_juicer"):
            raise ImportError("simulated missing DJ")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _block_dj)
    rewrite, drop = _build_ray_rewrite_map()
    assert rewrite == {}
    assert drop == {}


def test_module_level_maps_match_fresh_build():
    """Module-level _RAY_DEDUP_REWRITE/_RAY_DEDUP_DROP_PARAMS equal fresh call."""
    from data_juicer_agents.tools.apply.submit_ray_job.logic import (
        _RAY_DEDUP_REWRITE as loaded_rewrite,
        _RAY_DEDUP_DROP_PARAMS as loaded_drop,
    )
    fresh_rewrite, fresh_drop = _build_ray_rewrite_map()
    assert loaded_rewrite == fresh_rewrite
    assert loaded_drop == fresh_drop
