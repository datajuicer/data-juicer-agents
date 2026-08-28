# -*- coding: utf-8 -*-
"""E2E tests pinning context tool behavior (list_system_config, list_dataset_fields, etc.)."""

from data_juicer_agents.tools.context.list_dataset_fields.logic import list_dataset_fields
from data_juicer_agents.tools.context.list_dataset_load_strategies.logic import (
    list_dataset_load_strategies,
)
from data_juicer_agents.tools.context.list_system_config.logic import list_system_config


class TestListSystemConfig:
    """Pin list_system_config behavior."""

    def test_returns_ok(self):
        result = list_system_config()
        assert result["ok"] is True
        assert result["total_count"] > 0

    def test_contains_known_fields(self):
        result = list_system_config()
        config = result["config"]
        assert "np" in config
        assert "executor_type" in config

    def test_filter_prefix(self):
        result = list_system_config(filter_prefix="cache")
        config = result["config"]
        assert all(k.startswith("cache") for k in config)

    def test_includes_descriptions(self):
        result = list_system_config(include_descriptions=True)
        config = result["config"]
        has_desc = any("description" in v for v in config.values())
        assert has_desc


class TestListDatasetFields:
    """Pin list_dataset_fields behavior."""

    def test_returns_ok(self):
        result = list_dataset_fields()
        assert result["ok"] is True
        assert result["total_count"] > 0

    def test_contains_known_fields(self):
        result = list_dataset_fields()
        fields = result["fields"]
        assert "export_path" in fields
        assert "text_keys" in fields

    def test_filter_prefix(self):
        result = list_dataset_fields(filter_prefix="export")
        fields = result["fields"]
        assert all(k.startswith("export") for k in fields)


class TestListDatasetLoadStrategies:
    """Pin list_dataset_load_strategies behavior."""

    def test_returns_ok(self):
        result = list_dataset_load_strategies()
        assert result["ok"] is True
        assert result["total_count"] > 0

    def test_has_local_strategy(self):
        result = list_dataset_load_strategies()
        strategies = result["strategies"]
        assert any(s["type"] == "local" for s in strategies)

    def test_executor_type_filter(self):
        result = list_dataset_load_strategies(executor_type="default")
        assert result["ok"] is True
        # All strategies should be compatible with 'default' executor
        assert result["total_count"] > 0
