# -*- coding: utf-8 -*-
"""E2E tests pinning DJConfigBridge and coerce_fields behavior after preflight cleanup."""

from data_juicer_agents.utils.dj_config_bridge import coerce_fields, get_dj_config_bridge


class TestDJConfigBridge:
    """Pin current behavior of DJConfigBridge methods."""

    def setup_method(self):
        self.bridge = get_dj_config_bridge()

    def test_get_known_op_names(self):
        known_ops = self.bridge.get_known_op_names()
        assert len(known_ops) > 100
        assert "remove_long_words_mapper" in known_ops
        assert "language_id_score_filter" in known_ops

    def test_get_known_op_names_excludes_fake(self):
        known_ops = self.bridge.get_known_op_names()
        assert "fake_op_xyz" not in known_ops

    def test_extract_system_config(self):
        config = self.bridge.extract_system_config()
        assert "np" in config
        assert "executor_type" in config

    def test_extract_dataset_config(self):
        config = self.bridge.extract_dataset_config()
        assert "export_path" in config
        assert "text_keys" in config

    def test_validate_valid_config(self):
        is_valid, errors = self.bridge.validate({"np": 4, "executor_type": "default"})
        assert is_valid is True
        assert errors == []

    def test_validate_invalid_executor_type(self):
        is_valid, errors = self.bridge.validate({"executor_type": "nonexistent"})
        assert is_valid is False
        assert len(errors) > 0

    def test_get_implemented_load_strategies(self):
        strategies = self.bridge.get_implemented_load_strategies()
        assert len(strategies) > 0
        assert all("type" in s for s in strategies)
        assert any(s["type"] == "local" for s in strategies)


class TestCoerceFields:
    """Pin current behavior of coerce_fields."""

    def test_int_coercion(self):
        coerced, errors = coerce_fields({"np": "4"})
        assert coerced["np"] == 4
        assert errors == []

    def test_bool_coercion_true(self):
        coerced, errors = coerce_fields({"use_cache": "true"})
        assert coerced["use_cache"] is True
        assert errors == []

    def test_bool_coercion_false(self):
        coerced, errors = coerce_fields({"op_fusion": "false"})
        assert coerced["op_fusion"] is False
        assert errors == []

    def test_int_coercion_failure(self):
        coerced, errors = coerce_fields({"np": "abc"})
        assert coerced["np"] == "abc"
        assert any("Cannot coerce" in e and "np" in e for e in errors)

    def test_bool_coercion_failure(self):
        coerced, errors = coerce_fields({"use_cache": "maybe"})
        assert coerced["use_cache"] == "maybe"
        assert any("Cannot coerce" in e for e in errors)

    def test_unknown_fields_passthrough(self):
        coerced, errors = coerce_fields({"unknown_field_xyz": "value"})
        assert coerced["unknown_field_xyz"] == "value"
        assert errors == []

    def test_empty_dict(self):
        coerced, errors = coerce_fields({})
        assert coerced == {}
        assert errors == []

    def test_already_correct_types(self):
        coerced, errors = coerce_fields({"np": 4, "use_cache": True})
        assert coerced["np"] == 4
        assert coerced["use_cache"] is True
        assert errors == []
