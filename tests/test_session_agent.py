# -*- coding: utf-8 -*-

from pathlib import Path

import pytest
import yaml

from data_juicer_agents.adapters.agentscope import invoke_tool_spec
from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent
from data_juicer_agents.capabilities.session.runtime import SessionState, SessionToolRuntime
from data_juicer_agents.capabilities.session.toolkit import get_session_tool_specs
from data_juicer_agents.core.tool import ToolContext, build_default_tool_registry, list_tool_specs


def test_session_agent_toolkit_uses_staged_plan_tools_not_plan_build():
    pytest.importorskip("agentscope")
    agent = DJSessionAgent(use_llm_router=False)
    toolkit = agent._build_toolkit()  # pylint: disable=protected-access
    names = set(toolkit.tools.keys())
    assert "build_dataset_spec" in names
    assert "build_process_spec" in names
    assert "build_system_spec" in names
    assert "assemble_plan" in names
    assert "plan_build" not in names
    assert "plan_generate" not in names
    assert "trace_run" not in names


def test_session_toolkit_selects_explicit_tools_without_session_tags():
    specs = get_session_tool_specs()
    names = [spec.name for spec in specs]
    all_names = {spec.name for spec in list_tool_specs()}

    assert {spec.name for spec in specs} == all_names
    assert all("session" not in spec.tags for spec in specs)
    assert "inspect_dataset" in names
    assert "retrieve_operators" in names
    assert "build_dataset_spec" in names
    assert "build_process_spec" in names
    assert "build_system_spec" in names
    assert "assemble_plan" in names
    assert "apply_recipe" in names
    assert "execute_shell_command" in names
    assert "plan_build" not in names
    assert "trace_run" not in names


def test_build_process_spec_is_deterministic_with_explicit_operators(tmp_path: Path):
    registry = build_default_tool_registry()
    ctx = ToolContext(working_dir=str(tmp_path), artifacts_dir=str(tmp_path / ".djx"))

    result = invoke_tool_spec(
        registry.get("build_process_spec"),
        ctx=ctx,
        raw_kwargs={
            "operators": [
                {"name": "text_length_filter", "params": {"max_len": 1500}},
            ],
        },
    )

    assert result["ok"] is True
    assert result["process_spec"]["operators"] == [
        {"name": "text_length_filter", "params": {"max_len": 1500}},
    ]


def test_session_agent_staged_plan_validate_save_with_explicit_payloads(tmp_path: Path, monkeypatch):
    dataset = tmp_path / "data.jsonl"
    dataset.write_text('{"text": "hello world"}\n', encoding="utf-8")
    export_path = tmp_path / "out" / "result.jsonl"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path = tmp_path / "saved_plan.yaml"

    registry = build_default_tool_registry()
    ctx = ToolContext(working_dir=str(tmp_path), artifacts_dir=str(tmp_path / ".djx"))

    monkeypatch.setattr(
        "data_juicer_agents.tools.retrieve.retrieve_operators.tool.retrieve_operator_candidates",
        lambda **_kwargs: {
            "ok": True,
            "retrieval_source": "llm",
            "candidate_count": 1,
            "candidates": [
                {
                    "operator_name": "text_length_filter",
                    "description": "Filter rows by text length.",
                    "operator_type": "filter",
                    "arguments_preview": ["max_len (int): maximum text length to keep."],
                }
            ],
            "notes": [],
        },
    )
    inspected = invoke_tool_spec(
        registry.get("inspect_dataset"),
        ctx=ctx,
        raw_kwargs={"dataset_path": str(dataset), "sample_size": 5},
    )
    assert inspected["ok"] is True

    retrieved = invoke_tool_spec(
        registry.get("retrieve_operators"),
        ctx=ctx,
        raw_kwargs={"intent": "filter rows longer than 1500 characters", "dataset_path": str(dataset)},
    )
    assert retrieved["ok"] is True
    assert retrieved["candidate_names"] == ["text_length_filter"]

    dataset_spec = invoke_tool_spec(
        registry.get("build_dataset_spec"),
        ctx=ctx,
        raw_kwargs={
            "intent": "filter rows longer than 1500 characters",
            "dataset_path": str(dataset),
            "export_path": str(export_path),
            "dataset_profile": inspected,
        },
    )
    assert dataset_spec["ok"] is True
    assert dataset_spec["dataset_spec"]["binding"]["text_keys"] == ["text"]

    process_spec = invoke_tool_spec(
        registry.get("build_process_spec"),
        ctx=ctx,
        raw_kwargs={
            "operators": [
                {"name": "text_length_filter", "params": {"max_len": 1500}},
            ],
        },
    )
    assert process_spec["ok"] is True
    assert process_spec["process_spec"]["operators"][0]["name"] == "text_length_filter"
    assert "warnings" in process_spec

    system_spec = invoke_tool_spec(
        registry.get("build_system_spec"),
        ctx=ctx,
        raw_kwargs={"custom_operator_paths": [], "np": 1},
    )
    assert system_spec["ok"] is True
    assert system_spec["system_spec"]["np"] == 1
    assert system_spec["warnings"]

    validated_dataset = invoke_tool_spec(
        registry.get("validate_dataset_spec"),
        ctx=ctx,
        raw_kwargs={"dataset_spec": dataset_spec["dataset_spec"], "dataset_profile": inspected},
    )
    assert validated_dataset["ok"] is True

    validated_process = invoke_tool_spec(
        registry.get("validate_process_spec"),
        ctx=ctx,
        raw_kwargs={"process_spec": process_spec["process_spec"]},
    )
    assert validated_process["ok"] is True
    assert any("deferred" in item for item in validated_process["warnings"])

    assembled = invoke_tool_spec(
        registry.get("assemble_plan"),
        ctx=ctx,
        raw_kwargs={
            "intent": "filter rows longer than 1500 characters",
            "dataset_spec": dataset_spec["dataset_spec"],
            "process_spec": process_spec["process_spec"],
            "system_spec": system_spec["system_spec"],
            "approval_required": True,
        },
    )
    assert assembled["ok"] is True
    assert assembled["action"] == "assemble_plan"
    # assert assembled["warnings"]
    assert assembled["plan"]["recipe"]["process"][0]["text_length_filter"]["max_len"] == 1500

    validated = invoke_tool_spec(
        registry.get("plan_validate"),
        ctx=ctx,
        raw_kwargs={"plan_payload": assembled["plan"]},
    )
    assert validated["ok"] is True
    # assert validated["warnings"]

    saved = invoke_tool_spec(
        registry.get("plan_save"),
        ctx=ctx,
        raw_kwargs={"plan_payload": assembled["plan"], "output_path": str(plan_path), "overwrite": True},
    )
    assert saved["ok"] is True
    payload = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    assert payload["plan_id"] == assembled["plan_id"]
    assert "workflow" not in payload
    assert payload["recipe"]["np"] == 1
    # assert payload["warnings"]


def test_session_runtime_remains_observational_after_tool_invocation(tmp_path: Path):
    runtime = SessionToolRuntime(state=SessionState(dataset_path="/tmp/original.jsonl"))
    ctx = ToolContext(
        working_dir=str(tmp_path),
        artifacts_dir=str(tmp_path / ".djx"),
        runtime_values={"session_runtime": runtime},
    )
    registry = build_default_tool_registry()

    result = invoke_tool_spec(
        registry.get("build_process_spec"),
        ctx=ctx,
        raw_kwargs={
            "operators": [{"name": "text_length_filter", "params": {"max_len": 100}}],
        },
    )

    assert result["ok"] is True
    assert runtime.state.process_spec is None
    assert runtime.state.dataset_path == "/tmp/original.jsonl"
