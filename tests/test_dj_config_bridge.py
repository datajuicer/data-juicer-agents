# -*- coding: utf-8 -*-

from data_juicer_agents.utils.dj_config_bridge import (
    DJConfigBridge,
    agent_managed_fields,
    coerce_fields,
    dataset_fields,
    get_dj_config_bridge,
    system_fields,
)


def test_get_dj_config_bridge_returns_singleton():
    """Test that get_dj_config_bridge returns the same instance."""
    bridge1 = get_dj_config_bridge()
    bridge2 = get_dj_config_bridge()
    assert bridge1 is bridge2


def test_get_default_config_returns_dict():
    """Test that get_default_config returns a dictionary with expected keys."""
    bridge = DJConfigBridge()
    config = bridge.get_default_config()

    assert isinstance(config, dict)
    # Should contain some common config keys
    assert "process" in config


def test_get_default_config_caches_result():
    """Test that get_default_config caches the result."""
    bridge = DJConfigBridge()
    config1 = bridge.get_default_config()
    config2 = bridge.get_default_config()
    assert config1 is config2


def test_extract_system_config_excludes_dataset_fields():
    """Test that extract_system_config excludes dataset fields and process."""
    bridge = DJConfigBridge()

    config = {
        "dataset_path": "/path/to/data",
        "export_path": "/path/to/export",
        "process": [{"filter": {}}],
        "np": 4,
        "text_keys": "text",
    }

    system_config = bridge.extract_system_config(config)

    assert "dataset_path" not in system_config
    assert "export_path" not in system_config
    assert "process" not in system_config
    assert "text_keys" not in system_config
    assert "np" in system_config
    assert system_config["np"] == 4


def test_extract_dataset_config_returns_dataset_fields():
    """Test that extract_dataset_config returns only dataset fields."""
    bridge = DJConfigBridge()

    config = {
        "dataset_path": "/path/to/data",
        "export_path": "/path/to/export",
        "np": 4,
        "text_keys": "text",
        "image_key": "image",
    }

    dataset_config = bridge.extract_dataset_config(config)

    assert dataset_config["dataset_path"] == "/path/to/data"
    assert dataset_config["export_path"] == "/path/to/export"
    assert dataset_config["text_keys"] == "text"
    assert dataset_config["image_key"] == "image"
    assert "np" not in dataset_config


def test_extract_process_config_returns_process_list():
    """Test that extract_process_config returns the process list."""
    bridge = DJConfigBridge()

    process = [{"text_length_filter": {"min_len": 10}}]
    config = {"process": process, "np": 4}

    result = bridge.extract_process_config(config)

    assert result == process


def test_get_param_descriptions_returns_dict():
    """Test that get_param_descriptions returns a dictionary."""
    bridge = DJConfigBridge()
    descriptions = bridge.get_param_descriptions()

    assert isinstance(descriptions, dict)
    # Should have some entries
    assert len(descriptions) > 0


def test_extract_system_config_returns_dict():
    """Test that extract_system_config returns a dictionary."""
    bridge = get_dj_config_bridge()
    schema = bridge.extract_system_config()

    assert isinstance(schema, dict)
    # project_name is now agent-managed, should NOT be in system config
    assert "project_name" not in schema
    # executor_type should be in system config
    assert "executor_type" in schema


def test_get_param_descriptions_has_project_name():
    """Test that bridge.get_param_descriptions() includes project_name."""
    bridge = get_dj_config_bridge()
    descriptions = bridge.get_param_descriptions()

    print("Parameter descriptions:", descriptions)

    assert isinstance(descriptions, dict)
    assert descriptions["project_name"] == "Name of your data process project."


def test_extract_system_config_with_none_uses_defaults():
    """Test that extract_system_config uses defaults when config is None."""
    bridge = DJConfigBridge()

    result = bridge.extract_system_config(None)

    assert isinstance(result, dict)
    # Should not contain dataset fields
    for field in dataset_fields:
        assert field not in result
    assert "process" not in result


def test_extract_dataset_config_with_none_uses_defaults():
    """Test that extract_dataset_config uses defaults when config is None."""
    bridge = DJConfigBridge()

    result = bridge.extract_dataset_config(None)

    assert isinstance(result, dict)
    # Should only contain dataset fields
    for key in result.keys():
        assert key in dataset_fields


# --- coerce_fields tests ---


def test_coerce_fields_str_to_bool():
    """Test that string booleans are coerced to Python bool."""
    # open_monitor has a bool default in DJ parser
    result, errors = coerce_fields({"open_monitor": "true"})
    assert result["open_monitor"] is True
    assert errors == []

    result, errors = coerce_fields({"open_monitor": "false"})
    assert result["open_monitor"] is False
    assert errors == []

    result, errors = coerce_fields({"open_monitor": "yes"})
    assert result["open_monitor"] is True
    assert errors == []

    result, errors = coerce_fields({"open_monitor": "0"})
    assert result["open_monitor"] is False
    assert errors == []

    # Non-parseable string should be kept as-is with an error
    result, errors = coerce_fields({"open_monitor": "maybe"})
    assert result["open_monitor"] == "maybe"
    assert len(errors) == 1


def test_coerce_fields_str_to_int():
    """Test that string integers are coerced to Python int."""
    # np has an int default in DJ parser
    result, errors = coerce_fields({"np": "8"})
    assert result["np"] == 8
    assert isinstance(result["np"], int)
    assert errors == []

    # Non-parseable string should be kept as-is with an error
    result, errors = coerce_fields({"np": "not_a_number"})
    assert result["np"] == "not_a_number"
    assert len(errors) == 1


def test_coerce_fields_str_to_float():
    """Test that string floats are coerced to Python float."""
    # data_probe_ratio has a float default in DJ parser
    result, errors = coerce_fields({"data_probe_ratio": "0.5"})
    assert result["data_probe_ratio"] == 0.5
    assert isinstance(result["data_probe_ratio"], float)
    assert errors == []


def test_coerce_fields_unknown_fields_passthrough():
    """Test that fields not registered in the parser are passed through unchanged."""
    result, errors = coerce_fields(
        {
            "totally_unknown_field": "some_value",
            "another_unknown": 42,
        }
    )
    assert result["totally_unknown_field"] == "some_value"
    assert result["another_unknown"] == 42
    assert errors == []


def test_coerce_fields_non_basic_type_passthrough():
    """Test that fields with non-basic target types are not converted."""
    # project_name has a str default; passing an int should keep it as-is
    result, errors = coerce_fields({"project_name": 1000})
    assert result["project_name"] == 1000
    assert errors == []

    # Already-correct types should pass through without conversion
    result, errors = coerce_fields({"np": 4})
    assert result["np"] == 4
    assert isinstance(result["np"], int)
    assert errors == []


def test_coerce_fields_empty_input():
    """Test that empty input returns empty output."""
    result, errors = coerce_fields({})
    assert result == {}
    assert errors == []


def test_coerce_fields_mixed_known_and_unknown():
    """Test mixed known and unknown fields are handled correctly."""
    result, errors = coerce_fields(
        {
            "open_monitor": "true",
            "np": "16",
            "my_custom_field": [1, 2, 3],
        }
    )
    assert result["open_monitor"] is True
    assert result["np"] == 16
    assert isinstance(result["np"], int)
    assert result["my_custom_field"] == [1, 2, 3]
    assert errors == []


# --- New bridge method tests ---


def test_validate_returns_tuple():
    """Test that bridge.validate() returns (bool, list) for valid config."""
    bridge = get_dj_config_bridge()
    is_valid, errors = bridge.validate({"dataset_path": "/tmp/test.jsonl"})
    assert isinstance(is_valid, bool)
    assert isinstance(errors, list)


def test_validate_rejects_unknown_key():
    """Test that bridge.validate() rejects unknown keys."""
    bridge = get_dj_config_bridge()
    is_valid, errors = bridge.validate({"totally_unknown_field": "abc"})
    assert is_valid is False
    assert len(errors) > 0


def test_validate_rejects_wrong_type():
    """Test that bridge.validate() rejects wrong field types."""
    bridge = get_dj_config_bridge()
    is_valid, errors = bridge.validate({"np": "not_a_number"})
    assert is_valid is False
    assert len(errors) > 0


def test_validate_passes_empty_dict():
    """Test that bridge.validate() passes with empty dict (no required fields)."""
    bridge = get_dj_config_bridge()
    is_valid, errors = bridge.validate({})
    assert is_valid is True
    assert errors == []


def test_get_op_valid_params_returns_dict():
    """Test that bridge.get_op_valid_params() returns a tuple of (dict, set)."""
    bridge = get_dj_config_bridge()
    op_param_map, known_ops = bridge.get_op_valid_params({"text_length_filter"})
    assert isinstance(op_param_map, dict)
    assert isinstance(known_ops, set)


# --- Field classification tests ---


def test_system_fields_and_dataset_fields_no_overlap():
    """Test that system_fields and dataset_fields have no overlap."""
    overlap = set(system_fields) & set(dataset_fields)
    assert overlap == set(), f"Overlap between system and dataset fields: {overlap}"


def test_agent_managed_fields_not_in_system_or_dataset():
    """Test that agent_managed_fields are not in system_fields or dataset_fields."""
    in_system = set(agent_managed_fields) & set(system_fields)
    in_dataset = set(agent_managed_fields) & set(dataset_fields)
    assert (
        in_system == set()
    ), f"agent_managed_fields overlap with system_fields: {in_system}"
    assert (
        in_dataset == set()
    ), f"agent_managed_fields overlap with dataset_fields: {in_dataset}"


def test_extract_system_config_uses_explicit_list():
    """Test that extract_system_config only returns fields from system_fields."""
    bridge = get_dj_config_bridge()
    system_config = bridge.extract_system_config()

    # All returned keys must be in system_fields
    for key in system_config:
        assert key in system_fields, f"Unexpected key '{key}' in system config"

    # agent_managed_fields should not appear
    for field in agent_managed_fields:
        assert (
            field not in system_config
        ), f"Agent-managed field '{field}' should not be in system config"


def test_extract_agent_managed_config():
    """Test that extract_agent_managed_config returns agent-managed fields."""
    bridge = get_dj_config_bridge()
    managed_config = bridge.extract_agent_managed_config()

    assert isinstance(managed_config, dict)
    assert "project_name" in managed_config
    assert managed_config["project_name"] == "hello_world"


def test_extract_agent_managed_config_with_custom_config():
    """Test extract_agent_managed_config with a custom config dict."""
    bridge = DJConfigBridge()
    config = {
        "project_name": "my_project",
        "job_id": "job_123",
        "np": 4,
    }
    managed = bridge.extract_agent_managed_config(config)
    assert managed == {"project_name": "my_project", "job_id": "job_123"}
    assert "np" not in managed
