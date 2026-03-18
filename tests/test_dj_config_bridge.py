# -*- coding: utf-8 -*-

from data_juicer_agents.utils.dj_config_bridge import (
    DJConfigBridge,
    get_dj_config_bridge,
    validate_system_config,
    get_system_config_schema,
    get_system_param_descriptions,
    dataset_fields,
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


def test_validate_system_config_returns_true_for_valid_config(monkeypatch):
    """Test that validate_system_config returns True for valid config."""

    def fake_validate_config(self, config):
        return True, []

    monkeypatch.setattr(DJConfigBridge, "validate_config", fake_validate_config)

    is_valid, errors = validate_system_config({"np": 4})
    assert is_valid is True
    assert errors == []


def test_validate_system_config_merges_with_defaults(monkeypatch):
    """Test that validate_system_config merges with defaults."""
    captured_config = {}

    def fake_validate_config(self, config):
        nonlocal captured_config
        captured_config = config
        return True, []

    monkeypatch.setattr(DJConfigBridge, "validate_config", fake_validate_config)

    validate_system_config({"np": 3})

    # Should have merged with defaults
    assert "np" in captured_config
    assert captured_config["np"] == 3
    # process should be removed
    assert "process" not in captured_config


def test_get_system_config_schema_returns_dict():
    """Test that get_system_config_schema returns a dictionary."""
    schema = get_system_config_schema()

    assert isinstance(schema, dict)
    assert schema["project_name"] == "hello_world"


def test_get_system_param_descriptions_returns_dict():
    """Test that get_system_param_descriptions returns a dictionary."""
    descriptions = get_system_param_descriptions()

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
