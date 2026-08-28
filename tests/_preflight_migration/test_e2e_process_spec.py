# -*- coding: utf-8 -*-
"""E2E tests pinning validate_process_spec_payload behavior after preflight migration."""

import pytest

from data_juicer_agents.tools.plan._shared.process_spec import (
    normalize_process_spec,
    validate_process_spec_payload,
)
from data_juicer_agents.tools.plan._shared.schema import ProcessOperator, ProcessSpec


class TestValidateProcessSpec:
    """Pin behavior of validate_process_spec_payload (now uses DJ preflight)."""

    def test_valid_op_no_errors(self):
        spec = ProcessSpec(operators=[ProcessOperator(name="remove_long_words_mapper", params={"min_len": 1})])
        errors, warnings = validate_process_spec_payload(spec)
        assert errors == []

    def test_unknown_op_detected(self):
        spec = ProcessSpec(operators=[ProcessOperator(name="totally_fake_op_xyz", params={})])
        errors, warnings = validate_process_spec_payload(spec)
        assert any("totally_fake_op_xyz" in e for e in errors)
        assert any("not found in registry" in e.lower() or "unknown operator" in e.lower() for e in errors)

    def test_unknown_param_detected_with_suggestion(self):
        spec = ProcessSpec(operators=[ProcessOperator(name="remove_long_words_mapper", params={"min_length": 1})])
        errors, warnings = validate_process_spec_payload(spec)
        assert any("min_length" in e for e in errors)
        assert any("min_len" in e for e in errors)

    def test_empty_operators_error(self):
        spec = ProcessSpec(operators=[])
        errors, warnings = validate_process_spec_payload(spec)
        assert any("must not be empty" in e for e in errors)

    def test_missing_name_error(self):
        spec = ProcessSpec(operators=[ProcessOperator(name="", params={})])
        errors, warnings = validate_process_spec_payload(spec)
        assert any("name is required" in e for e in errors)

    def test_non_dict_params_error(self):
        spec = ProcessSpec(operators=[ProcessOperator(name="remove_long_words_mapper", params="bad")])
        errors, warnings = validate_process_spec_payload(spec)
        assert any("must be an object" in e for e in errors)

    def test_multiple_valid_ops(self):
        spec = ProcessSpec(operators=[
            ProcessOperator(name="remove_long_words_mapper", params={"min_len": 1, "max_len": 100}),
            ProcessOperator(name="language_id_score_filter", params={"lang": "en", "min_score": 0.8}),
        ])
        errors, warnings = validate_process_spec_payload(spec)
        assert errors == []

    def test_multiple_errors_collected(self):
        spec = ProcessSpec(operators=[
            ProcessOperator(name="totally_fake_op_xyz", params={}),
            ProcessOperator(name="remove_long_words_mapper", params={"min_length": 1}),
        ])
        errors, warnings = validate_process_spec_payload(spec)
        assert len(errors) >= 2

    def test_type_mismatch_detected(self):
        """DJ preflight now catches param type mismatches (new capability)."""
        spec = ProcessSpec(operators=[ProcessOperator(name="remove_long_words_mapper", params={"min_len": "hello"})])
        errors, warnings = validate_process_spec_payload(spec)
        assert any("min_len" in e and "int" in e for e in errors)


class TestNormalizeProcessSpec:
    """Pin current behavior of normalize_process_spec."""

    def test_strips_whitespace(self):
        spec = ProcessSpec(operators=[
            ProcessOperator(name="  remove_long_words_mapper  ", params={"min_len": 1}),
        ])
        result = normalize_process_spec(spec)
        assert result.operators[0].name == "remove_long_words_mapper"

    def test_skips_empty_names(self):
        spec = ProcessSpec(operators=[
            ProcessOperator(name="remove_long_words_mapper", params={"min_len": 1}),
            ProcessOperator(name="", params={}),
            ProcessOperator(name="language_id_score_filter", params={"lang": "en"}),
        ])
        result = normalize_process_spec(spec)
        assert len(result.operators) == 2
        assert result.operators[0].name == "remove_long_words_mapper"
        assert result.operators[1].name == "language_id_score_filter"

    def test_empty_raises(self):
        spec = ProcessSpec(operators=[ProcessOperator(name="", params={})])
        with pytest.raises(ValueError, match="at least one operator"):
            normalize_process_spec(spec)

    def test_non_dict_params_coerced_to_empty(self):
        spec = ProcessSpec(operators=[ProcessOperator(name="remove_long_words_mapper", params=None)])
        result = normalize_process_spec(spec)
        assert result.operators[0].params == {}
