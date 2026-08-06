# -*- coding: utf-8 -*-

import json

import pytest

from data_juicer_agents.adapters.agentscope import (
    build_agentscope_json_schema,
    build_agentscope_tool_function,
    compact_payload_for_model,
    tool_result_compaction_enabled,
)
from data_juicer_agents.core.tool import ToolContext, build_default_tool_registry


def test_build_agentscope_json_schema_uses_input_model():
    spec = build_default_tool_registry().get("retrieve_operators")
    schema = build_agentscope_json_schema(spec)

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "retrieve_operators"
    assert "intent" in schema["function"]["parameters"]["properties"]
    assert "top_k" in schema["function"]["parameters"]["properties"]
    assert schema["function"]["parameters"]["properties"]["mode"]["enum"] == ["auto", "bm25", "regex", "grep"]


def test_build_agentscope_json_schema_for_retrieve_operators_api():
    spec = build_default_tool_registry().get("retrieve_operators_api")
    schema = build_agentscope_json_schema(spec)

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "retrieve_operators_api"
    assert schema["function"]["parameters"]["properties"]["mode"]["enum"] == ["auto", "llm"]


def test_build_process_spec_schema_stays_shallow_for_agent_calls():
    spec = build_default_tool_registry().get("build_process_spec")
    schema = build_agentscope_json_schema(spec)
    params = schema["function"]["parameters"]

    assert schema["function"]["name"] == "build_process_spec"
    assert params["required"] == ["operators"]
    assert "operators" in params["properties"]
    assert "$defs" not in params
    assert "fill appropriate params" in params["properties"]["operators"]["description"]
    assert params["properties"]["operators"]["items"]["required"] == ["name", "params"]


def test_build_agentscope_tool_function_uses_arg_preview():
    pytest.importorskip("agentscope")
    spec = build_default_tool_registry().get("execute_python_code")
    seen = {}

    def fake_runtime_invoke(tool_name, args, fn):
        seen["tool_name"] = tool_name
        seen["args"] = dict(args)
        return fn()

    func = build_agentscope_tool_function(
        spec,
        ctx_factory=lambda: ToolContext(),
        runtime_invoke=fake_runtime_invoke,
    )
    long_code = "print('x')\n" * 300
    response = func(code=long_code, timeout=5)
    payload = json.loads(response.content[0]["text"])

    assert seen["tool_name"] == "execute_python_code"
    assert "[truncated" in seen["args"]["code"]
    assert payload["action"] == "execute_python_code"


def test_tool_result_compaction_can_be_disabled(monkeypatch):
    pytest.importorskip("agentscope")
    spec = build_default_tool_registry().get("execute_python_code")

    def fake_runtime_invoke(_tool_name, _args, _fn):
        return {
            "ok": True,
            "action": "execute_python_code",
            "stdout": "x" * 6000,
            "stderr": "",
            "returncode": 0,
        }

    monkeypatch.setenv("DJA_TOOL_RESULT_COMPACTION_ENABLED", "false")
    func = build_agentscope_tool_function(
        spec,
        ctx_factory=lambda: ToolContext(),
        runtime_invoke=fake_runtime_invoke,
    )
    payload = json.loads(func(code="print('x')", timeout=5).content[0]["text"])

    assert tool_result_compaction_enabled() is False
    assert payload["stdout"] == "x" * 6000


def test_tool_result_compaction_enabled_by_default(monkeypatch):
    monkeypatch.delenv("DJA_TOOL_RESULT_COMPACTION_ENABLED", raising=False)
    assert tool_result_compaction_enabled() is True


def test_compact_payload_keeps_error_details_for_failed_tools():
    payload = {
        "ok": False,
        "action": "execute_bash",
        "error_type": "command_failed",
        "message": "boom",
        "stderr": "trace line\n" * 800,
    }

    compact = compact_payload_for_model("execute_bash", payload)

    assert compact["ok"] is False
    assert compact["error_type"] == "command_failed"
    assert "trace line" in compact["stderr"]
    assert len(compact["stderr"]) < len(payload["stderr"])


def test_compact_payload_truncates_execute_bash_stdout_keeps_status():
    payload = {
        "ok": True,
        "action": "execute_bash",
        "returncode": 0,
        "command": "ls",
        "stdout": "line\n" * 5000,
    }

    compact = compact_payload_for_model("execute_bash", payload)

    assert compact["returncode"] == 0
    assert compact["command"] == "ls"
    assert len(compact["stdout"]) < len(payload["stdout"])


def test_compact_payload_caps_candidates_but_reports_total():
    candidates = [
        {"operator_name": f"op_{i}", "description": "d" * 900, "score": 0.9}
        for i in range(25)
    ]
    payload = {"ok": True, "candidates": candidates, "mode": "bm25"}

    compact = compact_payload_for_model("retrieve_operators", payload)

    assert compact["candidate_count"] == 25
    assert len(compact["candidates"]) == 10
    assert compact["candidates"][0]["operator_name"] == "op_0"
    assert len(compact["candidates"][0]["description"]) < 900


def test_compact_catalog_reports_visible_operator_count():
    operators = [
        {"operator_name": f"op_{index}", "description": "short"}
        for index in range(25)
    ]
    payload = {
        "ok": True,
        "total_count": 40,
        "returned_count": 25,
        "operators": operators,
        "include_parameters": False,
    }

    compact = compact_payload_for_model("list_operator_catalog", payload)

    assert compact["total_count"] == 40
    assert compact["returned_count"] == 25
    assert compact["compacted_count"] == 10
    assert compact["compacted_count"] == len(compact["operators"])


def test_compact_catalog_count_matches_short_operator_list():
    operators = [{"operator_name": f"op_{index}"} for index in range(3)]
    payload = {
        "ok": True,
        "total_count": 3,
        "returned_count": 3,
        "operators": operators,
    }

    compact = compact_payload_for_model("list_operator_catalog", payload)

    assert compact["compacted_count"] == 3
    assert compact["compacted_count"] == compact["returned_count"]


def test_compact_payload_unknown_tool_falls_back_to_generic_shrink():
    payload = {"ok": True, "blob": "x" * 9000, "nested": {"detail": "y" * 9000}}

    compact = compact_payload_for_model("some_future_tool", payload)

    assert len(compact["blob"]) < 9000
    assert len(compact["nested"]["detail"]) < 9000


def test_compact_payload_handles_non_dict_payload():
    compact = compact_payload_for_model("execute_bash", "raw text " * 500)

    assert compact["ok"] is True
    assert len(compact["result"]) < len("raw text " * 500)
