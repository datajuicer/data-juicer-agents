# -*- coding: utf-8 -*-

from data_juicer_agents.core.tool import ToolArtifact, ToolResult, build_default_tool_registry
from data_juicer_agents.core.tool.catalog import ALL_TOOL_GROUPS, iter_tool_group_names, load_all_tool_specs


def test_default_tool_registry_contains_core_specs():
    registry = build_default_tool_registry()
    names = set(registry.names())
    assert "inspect_dataset" in names
    assert "retrieve_operators" in names
    assert "build_dataset_spec" in names
    assert "build_process_spec" in names
    assert "assemble_plan" in names
    assert "apply_recipe" in names
    assert "execute_shell_command" in names
    assert "get_session_context" not in names
    assert "set_session_context" not in names
    assert "plan_build" not in names

    assert all("session" not in registry.get(name).tags for name in names)


def test_tool_catalog_discovers_group_definitions():
    groups = iter_tool_group_names()
    assert groups == sorted(groups)
    assert "context" in groups
    assert "retrieve" in groups
    assert "plan" in groups
    assert "apply" in groups
    assert tuple(groups) == ALL_TOOL_GROUPS

    discovered_names = {spec.name for spec in load_all_tool_specs()}
    assert "inspect_dataset" in discovered_names
    assert "retrieve_operators" in discovered_names
    assert "build_dataset_spec" in discovered_names
    assert "build_process_spec" in discovered_names
    assert "assemble_plan" in discovered_names
    assert "plan_build" not in discovered_names


def test_tool_result_to_payload_merges_defaults():
    result = ToolResult.failure(
        summary="apply failed",
        error_type="apply_failed",
        data={"plan_path": "/tmp/plan.yaml"},
        next_actions=["retry"],
    )
    result.artifacts.append(ToolArtifact(path="/tmp/out.jsonl", description="export"))

    payload = result.to_payload(action="apply_recipe")

    assert payload["ok"] is False
    assert payload["action"] == "apply_recipe"
    assert payload["message"] == "apply failed"
    assert payload["error_type"] == "apply_failed"
    assert payload["plan_path"] == "/tmp/plan.yaml"
    assert payload["next_actions"] == ["retry"]
    assert payload["artifacts"][0]["path"] == "/tmp/out.jsonl"
